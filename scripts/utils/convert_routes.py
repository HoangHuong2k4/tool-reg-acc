import re

with open('gpt_signup_hybrid-main/web/icloud_routes.py', 'r') as f:
    code = f.read()

# 1. Imports
code = code.replace("from fastapi import APIRouter, HTTPException, Query", "from flask import Blueprint, request, jsonify\nfrom pydantic import BaseModel, ValidationError")
code = code.replace("from fastapi.responses import JSONResponse", "")

# 2. Router definition
code = code.replace("def build_icloud_router() -> APIRouter:", "")
code = code.replace("    router = APIRouter()", "icloud_bp = Blueprint('icloud', __name__)")
code = code.replace("    return router", "")

# 3. Route decorators
code = re.sub(r'    @router\.get\("([^"]+)"\)', r'@icloud_bp.route("\1", methods=["GET"])', code)
code = re.sub(r'    @router\.post\("([^"]+)"\)', r'@icloud_bp.route("\1", methods=["POST"])', code)
code = re.sub(r'    @router\.delete\("([^"]+)"\)', r'@icloud_bp.route("\1", methods=["DELETE"])', code)
code = re.sub(r'    @router\.put\("([^"]+)"\)', r'@icloud_bp.route("\1", methods=["PUT"])', code)

# Fix indentation since it was inside build_icloud_router
code = "\n".join([line[4:] if line.startswith("    ") else line for line in code.split("\n")])

# 4. JSON responses
code = re.sub(r'JSONResponse\(content=(.*?)(?:,\s*status_code=(\d+))?\)', r'jsonify(\1), \2' if r'\2' else r'jsonify(\1)', code)
code = code.replace('JSONResponse(content=resp_body)', 'jsonify(resp_body)')
code = code.replace('JSONResponse(content=resp)', 'jsonify(resp)')
code = code.replace('JSONResponse(content=status_data)', 'jsonify(status_data)')
code = code.replace('JSONResponse(status_code=503, content=', 'jsonify(')
code = code.replace('raise HTTPException(status_code=400, detail=', 'return jsonify({"error": ')
code = code.replace('raise HTTPException(status_code=404, detail=', 'return jsonify({"error": ')
code = code.replace('raise HTTPException(status_code=409, detail=', 'return jsonify({"error": ')
code = code.replace('raise HTTPException(status_code=500, detail=', 'return jsonify({"error": ')
code = code.replace('raise HTTPException(status_code=503, detail=', 'return jsonify({"error": ')
code = re.sub(r'return jsonify\(\{"error":\s*(.+?)\)\s*(?=\n|$)', r'return jsonify({"error": \1}), 400', code)

# 5. Fastapi Dependency extraction (replace `req: MyModel` with `req = MyModel(**request.json)`)
def replacer(match):
    func_name = match.group(1)
    params = match.group(2)
    # Find req: Model
    p = re.search(r'(\w+):\s*([A-Z]\w+Request|[A-Z]\w+)', params)
    body_str = ""
    if p:
        var_name = p.group(1)
        model_name = p.group(2)
        body_str = f"\n    try:\n        {var_name} = {model_name}(**request.get_json() or {{}})\n    except ValidationError as e:\n        return jsonify({{\"detail\": e.errors()}}), 422"
    
    return f"async def {func_name}():{body_str}"

code = re.sub(r'async def ([a-zA-Z0-9_]+)\(([^)]*)\):', replacer, code)

with open('src/web/routes_icloud.py', 'w') as f:
    f.write(code)
