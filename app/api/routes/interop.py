import os
import xml.etree.ElementTree as ET
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.api import deps
from app.models.project import Project
from app.models.user import User

router = APIRouter()

def parse_xmi(content: bytes) -> dict:
    import re
    xml_text = content.decode('utf-8', errors='ignore')
    
    nodes = []
    edges = []
    x_pos = 100
    y_pos = 100
    
    # --- METHOD 1: STACK PARSER (Advanced) ---
    stack = []
    current_class = None
    tag_pattern = re.compile(r'<\s*(/?)\s*([\w:\.\-]+)([^>]*?)(/?)>', re.DOTALL)
    
    for match in tag_pattern.finditer(xml_text):
        is_closing = match.group(1) == '/'
        tag_name = match.group(2).lower()
        attrs_str = match.group(3)
        is_self_closing = match.group(4) == '/'
        
        attr_dict = {}
        attr_matches = re.findall(r'([\w:\.\-]+)\s*=\s*["\']([^"\']*)["\']', attrs_str)
        for k, v in attr_matches:
            attr_dict[k.lower()] = v
            
        if not is_closing:
            stack.append((tag_name, attr_dict))
            
            is_class = False
            if 'class' in tag_name: is_class = True
            elif 'type' in attr_dict and 'class' in attr_dict['type'].lower(): is_class = True
            elif 'xmi:type' in attr_dict and 'class' in attr_dict['xmi:type'].lower(): is_class = True
                
            if is_class:
                cls_id = attr_dict.get('xmi:id') or attr_dict.get('xmi.id') or attr_dict.get('id')
                cls_name = attr_dict.get('name', 'Unknown')
                if cls_id and 'earootclass' not in cls_name.lower() and 'diagram' not in tag_name:
                    current_class = {
                        "id": str(cls_id),
                        "type": "tableNode",
                        "position": {"x": x_pos, "y": y_pos},
                        "data": {
                            "tableName": cls_name,
                            "columns": []
                        }
                    }
                    nodes.append(current_class)
                    x_pos += 250
                    if x_pos > 1000:
                        x_pos = 100; y_pos += 200
            
            is_attr = False
            if 'attribute' in tag_name or 'property' in tag_name: is_attr = True
            elif 'type' in attr_dict and ('attribute' in attr_dict['type'].lower() or 'property' in attr_dict['type'].lower()): is_attr = True
            elif 'xmi:type' in attr_dict and ('attribute' in attr_dict['xmi:type'].lower() or 'property' in attr_dict['xmi:type'].lower()): is_attr = True
                
            if 'generalization' in tag_name or ('type' in attr_dict and 'generalization' in attr_dict['type'].lower()) or ('xmi:type' in attr_dict and 'generalization' in attr_dict['xmi:type'].lower()):
                gen_id = attr_dict.get('xmi:id') or attr_dict.get('xmi.id') or attr_dict.get('id')
                gen_target = attr_dict.get('general') or attr_dict.get('supertype')
                gen_source = attr_dict.get('subtype') or (current_class['id'] if current_class else None)
                if gen_id and gen_target and gen_source:
                    edges.append({
                        "id": str(gen_id),
                        "source": str(gen_source),
                        "target": str(gen_target),
                        "type": "relationEdge",
                        "data": {"relationType": "Generalize"}
                    })
                    
            if 'taggedvalue' in tag_name and attr_dict.get('tag') == 'associationclass':
                assoc_class_val = attr_dict.get('value')
                if current_class and assoc_class_val:
                    if 'association_classes' not in current_class:
                        current_class['association_classes'] = []
                    current_class['association_classes'].append(assoc_class_val)

            if 'dependency' in tag_name or 'realization' in tag_name or ('type' in attr_dict and ('dependency' in attr_dict['type'].lower() or 'realization' in attr_dict['type'].lower())) or ('xmi:type' in attr_dict and ('dependency' in attr_dict['xmi:type'].lower() or 'realization' in attr_dict['xmi:type'].lower())):
                dep_id = attr_dict.get('xmi:id') or attr_dict.get('xmi.id') or attr_dict.get('id')
                client = attr_dict.get('client')
                supplier = attr_dict.get('supplier')
                if dep_id and client and supplier:
                    rel_type = "Dependency"
                    if 'realization' in tag_name or ('type' in attr_dict and 'realization' in attr_dict['type'].lower()) or ('xmi:type' in attr_dict and 'realization' in attr_dict['xmi:type'].lower()):
                        rel_type = "Realize"
                    edges.append({
                        "id": str(dep_id),
                        "source": str(client),
                        "target": str(supplier),
                        "type": "relationEdge",
                        "data": {"relationType": rel_type}
                    })

            if is_attr and current_class:
                col_name = attr_dict.get('name')
                if col_name:
                    current_class['data']['columns'].append({
                        "name": col_name,
                        "type": "VARCHAR",
                        "isPrimary": col_name.lower() == 'id',
                        "visibility": attr_dict.get('visibility', 'private')
                    })
                    
            is_assoc = False
            if 'association' in tag_name and 'end' not in tag_name: is_assoc = True
            elif 'type' in attr_dict and 'association' in attr_dict['type'].lower(): is_assoc = True
            elif 'xmi:type' in attr_dict and 'association' in attr_dict['xmi:type'].lower(): is_assoc = True
                
            if is_assoc:
                assoc_id = attr_dict.get('xmi:id') or attr_dict.get('xmi.id') or attr_dict.get('id')
                member_end = attr_dict.get('memberend')
                ends = []
                if member_end: ends = member_end.split()
                if len(ends) >= 2 and assoc_id:
                     edges.append({
                        "id": str(assoc_id),
                        "source": str(ends[0]),
                        "target": str(ends[1]),
                        "type": "relationEdge",
                        "data": {"relationType": "Associate"}
                     })
                     
            is_end = False
            if 'end' in tag_name or 'connection' in tag_name: is_end = True
                 
            if is_end:
                 in_assoc = False
                 assoc_id = None
                 for p_tag, p_attr in reversed(stack[:-1]):
                     p_is_assoc = False
                     if 'association' in p_tag and 'end' not in p_tag: p_is_assoc = True
                     elif 'type' in p_attr and 'association' in p_attr['type'].lower(): p_is_assoc = True
                     elif 'xmi:type' in p_attr and 'association' in p_attr['xmi:type'].lower(): p_is_assoc = True
                     if p_is_assoc:
                         assoc_id_candidate = p_attr.get('xmi:id') or p_attr.get('xmi.id') or p_attr.get('id')
                         if assoc_id_candidate:
                             in_assoc = True
                             assoc_id = assoc_id_candidate
                             break
                         
                 if in_assoc and assoc_id:
                     aggregation = attr_dict.get('aggregation')
                     if aggregation:
                         existing_edge = next((e for e in edges if e['id'] == str(assoc_id)), None)
                         if existing_edge:
                             end_type_temp = attr_dict.get('type') or attr_dict.get('participant') or attr_dict.get('xmi:idref')
                             if aggregation.lower() in ['composite', 'shared']:
                                 existing_edge['data']['relationType'] = 'Compose' if aggregation.lower() == 'composite' else 'Aggregate'
                                 if end_type_temp:
                                     existing_edge['aggregation_part'] = str(end_type_temp)

                     end_type = attr_dict.get('type') or attr_dict.get('participant') or attr_dict.get('xmi:idref')
                     if end_type and 'property' not in end_type.lower():
                         if ' ' in end_type: # xmi:idref="1 2"
                             es = end_type.split()
                             edges.append({
                                "id": str(assoc_id),
                                "source": str(es[0]),
                                "target": str(es[1] if len(es)>1 else es[0]),
                                "type": "relationEdge",
                                "data": {"relationType": "Associate"}
                             })
                         else:
                             edge = next((e for e in edges if e['id'] == str(assoc_id)), None)
                             if not edge:
                                 edges.append({
                                    "id": str(assoc_id),
                                    "source": str(end_type),
                                    "target": "",
                                    "type": "relationEdge",
                                    "data": {"relationType": "Associate"}
                                 })
                             else:
                                 if edge['source'] != str(end_type) and not edge['target']:
                                     edge['target'] = str(end_type)
                                 
                                 # Apply aggregation if found
                                 if aggregation:
                                     if aggregation.lower() == 'composite': edge['data']['relationType'] = 'Compose'
                                     elif aggregation.lower() == 'shared': edge['data']['relationType'] = 'Aggregate'
                                 
            if is_self_closing:
                stack.pop()
                
        else:
            if stack:
                popped_tag, _ = stack.pop()
                if current_class and ('class' in popped_tag or 'packagedelement' in popped_tag):
                    if not any(c['name'].lower() == 'id' for c in current_class['data']['columns']):
                        current_class['data']['columns'].insert(0, {"name": "id", "type": "INTEGER", "isPrimary": True, "visibility": "private"})
                    current_class = None

    # Process Diamond Polarity (Swap so target is the container)
    for edge in edges:
        if 'aggregation_part' in edge:
            # The part has the aggregation attribute, so the container is the OTHER end.
            # We want the diamond on the container. React Flow puts the diamond on the TARGET.
            # So TARGET must be the OTHER end (not the part).
            part = edge['aggregation_part']
            if edge['target'] == part:
                # Target is the part, but we want target to be the container. Swap!
                edge['source'], edge['target'] = edge['target'], edge['source']
            del edge['aggregation_part']

    # Process Association Classes
    for node in nodes:
        if 'association_classes' in node:
            for assoc_val in node['association_classes']:
                assoc_edge = next((e for e in edges if e['id'] == str(assoc_val)), None)
                if assoc_edge:
                    edges.append({
                        "id": f"assoc_class_{node['id']}_{assoc_edge['source']}",
                        "source": str(node['id']),
                        "target": str(assoc_edge['source']),
                        "type": "relationEdge",
                        "data": {"relationType": "Dependency"}
                    })
                    edges.append({
                        "id": f"assoc_class_{node['id']}_{assoc_edge['target']}",
                        "source": str(node['id']),
                        "target": str(assoc_edge['target']),
                        "type": "relationEdge",
                        "data": {"relationType": "Dependency"}
                    })
            del node['association_classes']

    edges = [e for e in edges if e.get('source') and e.get('target')]
    
    # --- METHOD 2: BRUTE FORCE REGEX (Fallback) ---
    if not nodes:
        print("Stack parser failed. Falling back to Brute Force Regex.")
        nodes = []
        x_pos = 100
        y_pos = 100
        class_pattern = re.compile(r'<[^>]*Class[^>]*>', re.IGNORECASE)
        for match in class_pattern.findall(xml_text):
            id_match = re.search(r'id="([^"]+)"', match, re.IGNORECASE)
            name_match = re.search(r'name="([^"]+)"', match, re.IGNORECASE)
            
            if id_match and name_match:
                cls_id = id_match.group(1)
                cls_name = name_match.group(1)
                if 'earootclass' not in cls_name.lower() and 'diagram' not in match.lower():
                    nodes.append({
                        "id": str(cls_id),
                        "type": "tableNode",
                        "position": {"x": x_pos, "y": y_pos},
                        "data": {
                            "tableName": cls_name,
                            "columns": [{"name": "id", "type": "INTEGER", "isPrimary": True, "visibility": "private"}]
                        }
                    })
                    x_pos += 250
                    if x_pos > 1000:
                        x_pos = 100
                        y_pos += 200

    if not nodes:
        raise Exception("No UML Classes found in XMI file.")
        
    return {"nodes": nodes, "edges": edges}

@router.get("/{project_id}/export/xmi")
def export_xmi(project_id: int, db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    canvas = project.canvas_data or {"nodes": [], "edges": []}
    xmi_root = ET.Element("xmi:XMI", {"xmi:version": "2.1", "xmlns:uml": "http://schema.omg.org/spec/UML/2.1", "xmlns:xmi": "http://schema.omg.org/spec/XMI/2.1"})
    model = ET.SubElement(xmi_root, "uml:Model", {"xmi:type": "uml:Model", "name": "Model", "xmi:id": "m1"})
    pkg = ET.SubElement(model, "packagedElement", {"xmi:type": "uml:Package", "xmi:id": "pkg1", "name": project.name or "Project"})
    for node in canvas.get("nodes", []):
        if node.get("type") == "tableNode":
            data = node.get("data", {})
            t_id = str(node.get("id"))
            t_name = data.get("tableName", "UnknownTable")
            cls_elem = ET.SubElement(pkg, "packagedElement", {"xmi:type": "uml:Class", "xmi:id": t_id, "name": t_name})
            for col in data.get("columns", []):
                col_name = col.get("name")
                attr_elem = ET.SubElement(cls_elem, "ownedAttribute", {"xmi:type": "uml:Property", "xmi:id": f"{t_id}_{col_name}", "name": col_name, "visibility": "public"})
                ET.SubElement(attr_elem, "type", {"xmi:type": "uml:PrimitiveType", "href": f"http://schema.omg.org/spec/UML/2.1/uml.xml#{col.get('type', 'String')}"})
    for edge in canvas.get("edges", []):
        s_id = str(edge.get("source"))
        t_id = str(edge.get("target"))
        e_id = str(edge.get("id"))
        rel_type = edge.get("data", {}).get("relationType", "Associate")
        if s_id and t_id:
            if rel_type == "Generalize":
                # Find the source class and append generalization
                for elem in pkg.findall("packagedElement"):
                    if elem.get("{http://schema.omg.org/spec/XMI/2.1}id") == s_id or elem.get("xmi:id") == s_id:
                        ET.SubElement(elem, "generalization", {"xmi:type": "uml:Generalization", "xmi:id": e_id, "general": t_id})
                        break
            elif rel_type in ["Dependency", "Realize"]:
                uml_type = "uml:Realization" if rel_type == "Realize" else "uml:Dependency"
                ET.SubElement(pkg, "packagedElement", {"xmi:type": uml_type, "xmi:id": e_id, "client": s_id, "supplier": t_id})
            else:
                # Associate, Compose, Aggregate
                assoc_elem = ET.SubElement(pkg, "packagedElement", {"xmi:type": "uml:Association", "xmi:id": e_id, "memberEnd": f"{e_id}_end1 {e_id}_end2"})
                
                # Source end
                end1_attrs = {"xmi:type": "uml:Property", "xmi:id": f"{e_id}_end1", "type": s_id, "association": e_id}
                
                # Target end
                end2_attrs = {"xmi:type": "uml:Property", "xmi:id": f"{e_id}_end2", "type": t_id, "association": e_id}
                
                if rel_type == "Compose":
                    end1_attrs["aggregation"] = "composite"
                elif rel_type == "Aggregate":
                    end1_attrs["aggregation"] = "shared"
                    
                ET.SubElement(assoc_elem, "ownedEnd", end1_attrs)
                ET.SubElement(assoc_elem, "ownedEnd", end2_attrs)
    xml_str = ET.tostring(xmi_root, encoding='utf-8', method='xml').decode('utf-8')
    xml_str = '<?xml version="1.0" encoding="windows-1252"?>\n' + xml_str
    return Response(content=xml_str, media_type="application/xml", headers={"Content-Disposition": f"attachment; filename=project_{project_id}.xml"})

@router.post("/{project_id}/import/xmi")
def import_xmi(project_id: int, file: UploadFile = File(...), db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    content = file.file.read()
    with open(r"c:\Users\chave\Desktop\db_designer_backend\scratch_debug_xmi.xml", "wb") as f:
        f.write(content)
    try:
        new_canvas = parse_xmi(content)
        project.canvas_data = new_canvas
        db.commit()
        return new_canvas
    except Exception as e:
        print(f"Error parsing XMI: {e}")
        import traceback; raise HTTPException(status_code=400, detail=f"Invalid XMI file: {str(e)} \n {traceback.format_exc()}")

@router.post("/import/xmi/new")
def import_xmi_new(file: UploadFile = File(...), db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user)):
    content = file.file.read()
    with open(r"c:\Users\chave\Desktop\db_designer_backend\scratch_debug_xmi.xml", "wb") as f:
        f.write(content)
    try:
        new_canvas = parse_xmi(content)
        project = Project(
            name=file.filename.replace('.xml', '') if file.filename else "Proyecto Importado",
            description="Proyecto importado desde archivo XMI",
            owner_id=current_user.id,
            canvas_data=new_canvas
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    except Exception as e:
        print(f"Error parsing XMI: {e}")
        import traceback; raise HTTPException(status_code=400, detail=f"Invalid XMI file: {str(e)} \n {traceback.format_exc()}")
