from app.main import app,get_file_by_id
from fastapi import HTTPException 
from relearn_exctract_text import extract_text


@app.post("/files/{file_id}/extract")
def post_file_on_db(file_id:int):
    file = get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404,detail='file not found')
    file_path = file.filepath
    extracted_text = extract_text(file_path)
    if file_path == None:
        return {'file is not extractble'}
    file.extracted_text = extracted_text
    return { "status":"extracted",
            "file_id":file_id,
            "length":len(extracted_text),
            "preview":extracted_text[:200]
            }        
        