import io
import zipfile
from jinja2 import Environment, FileSystemLoader
import os

def to_camel_case(snake_str):
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def to_pascal_case(snake_str):
    components = snake_str.split('_')
    return ''.join(x.title() for x in components)

def sql_to_java_type(sql_type):
    mapping = {
        'INTEGER': 'Integer',
        'INT': 'Integer',
        'VARCHAR': 'String',
        'TEXT': 'String',
        'BOOLEAN': 'Boolean',
        'DATE': 'java.time.LocalDate',
        'TIMESTAMP': 'java.time.LocalDateTime',
        'DECIMAL': 'java.math.BigDecimal',
        'FLOAT': 'Float',
        'DOUBLE': 'Double'
    }
    return mapping.get(sql_type.upper(), 'String')

def generate_project_zip(diagram_data: dict) -> io.BytesIO:
    env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))
    
    zip_buffer = io.BytesIO()
    
    def render_clean(template_name, **kwargs):
        rendered = env.get_template(template_name).render(**kwargs)
        # Strip UTF-8 BOM if present, as javac fails on it
        if rendered.startswith('\ufeff'):
            rendered = rendered[1:]
        return rendered

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Base project files
        zip_file.writestr('pom.xml', render_clean('pom.xml'))
        zip_file.writestr('src/main/resources/application.properties', render_clean('application.properties.jinja2'))
        zip_file.writestr('src/main/java/com/dbdesigner/Application.java', render_clean('Application.java.jinja2'))
        
        nodes = diagram_data.get('nodes', [])
        edges = diagram_data.get('edges', [])
        
        tables = []
        
        for node in nodes:
            if node.get('type') != 'tableNode':
                continue
            
            table_name = node['data']['tableName']
            class_name = to_pascal_case(table_name)
            columns = []
            fks = []
            pk_camel = 'Id'
            
            for col in node['data']['columns']:
                java_type = sql_to_java_type(col['type'])
                camel_name = to_camel_case(col['name'])
                if col.get('isPrimary'):
                    pk_camel = camel_name.capitalize()
                    
                # Basic FK detection (ends with _id or is related via edges)
                is_fk = col['name'].endswith('_id') and not col.get('isPrimary')
                fk_class = to_pascal_case(col['name'][:-3]) if is_fk else None
                
                columns.append({
                    'name': col['name'],
                    'camel_name': camel_name,
                    'sql_type': col['type'],
                    'java_type': java_type,
                    'is_primary': col.get('isPrimary', False),
                    'is_fk': is_fk,
                    'fk_class': fk_class
                })
                
                if is_fk:
                    fks.append({
                        'column': col['name'],
                        'target_table': col['name'][:-3],
                        'target_column': 'id'
                    })
            
            tables.append({
                'table_name': table_name,
                'class_name': class_name,
                'columns': columns,
                'fks': fks,
                'pk_camel': pk_camel,
                'custom_procedures': node['data'].get('customProcedures', [])
            })
            
        # Write schema.sql
        zip_file.writestr('src/main/resources/schema.sql', render_clean('schema.sql.jinja2', tables=tables))
        
        # Write Java classes
        for table in tables:
            class_name = table['class_name']
            
            # Simple OneToMany resolution
            one_to_many = []
            for other_table in tables:
                for col in other_table['columns']:
                    if col['is_fk'] and col['fk_class'] == class_name:
                        one_to_many.append({
                            'mapped_by': to_camel_case(col['name']),
                            'target_class': other_table['class_name'],
                            'field_name': to_camel_case(other_table['table_name']) + 'List'
                        })
            table['one_to_many'] = one_to_many

            zip_file.writestr(f'src/main/java/com/dbdesigner/model/{class_name}.java', 
                              render_clean('Entity.java.jinja2', **table))
            
            zip_file.writestr(f'src/main/java/com/dbdesigner/repository/{class_name}Repository.java', 
                              render_clean('Repository.java.jinja2', **table))
            
            zip_file.writestr(f'src/main/java/com/dbdesigner/service/{class_name}Service.java', 
                              render_clean('Service.java.jinja2', **table))
            
            zip_file.writestr(f'src/main/java/com/dbdesigner/controller/{class_name}Controller.java', 
                              render_clean('Controller.java.jinja2', **table))

        # Generar Documentacion Markdown
        zip_file.writestr('API_DOCS.md', render_clean('API_DOCS.md.jinja2', tables=tables))
    
    zip_buffer.seek(0)
    return zip_buffer
