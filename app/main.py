#here we import fastapi and uploadfile -  it handle the file uploading thing without adding unnecessiory things and import File - it is a file class 
from fastapi import FastAPI,UploadFile,File , HTTPException
# import os to handle os level task like make filder and join file paths
import os
from app.services.pdf_extractor import extract_text_from_pdf
from crud_uploaded_file import create_uploaded_file , files, get_file_by_id,delete_file,update_extracted_text

# just a variable
UPLOAD_DIR="uploads"
# os make new folder with name of uploads , exsist_ok = if not created create onece and if already exsist do nothing
os.makedirs(UPLOAD_DIR,exist_ok=True)

#inharit the fastapi method which provide us fastapi methods like creating routs and many more
app = FastAPI()


# decoratior which take get request on /  meens root 
@app.get("/")
def invoice_parser():
    # return ok
    return {"message":"Wellcome to Invoice Parser"}

# it is a post request where we send data to fastapi for upload url path
@app.post('/files')
# async fun because we have to handle file reading and uploading which takes time and file inharit uploadFile to access there methods which is type of File and ... meens required
async def upload_file(file:UploadFile=File(...)):
    # it allowed only these type of files other then that not allowed to upload
    ALLOWED = {"image/jpeg", "image/png", "application/pdf"}
    if file.content_type not in ALLOWED:
        return {"error": "Only JPG, PNG, PDF allowed"}

    # read the file file is in byte object and await meens it read 1st then execute next line
    readFile = await file.read()
    # variable which create unique file path to add on uploads folder
    filePath = os.path.join(UPLOAD_DIR,file.filename)
    # open filePath as wb - write bytes to write images in byte obj form as f and write it create new file ex - /uploads/ac.pdf if not exsist and write
    with open(filePath,'wb') as f:
        f.write(readFile)
    record = create_uploaded_file(filename=file.filename,size=len(readFile),filepath=filePath)
# return success msg with filename and size of file
    return {"id":record.id,"filename":file.filename , "size": len(readFile)}


@app.get('/get_upload_data')
def get_documents():
    return files()

@app.get('/files/{file_id}')
def get_file(file_id:int):
    file =  get_file_by_id(file_id)
    if file:
        return file
    else:
        raise HTTPException(status_code=404,detail='file not found')

@app.delete('/files/{file_id}')
def del_file(file_id:int):
    res = delete_file(file_id)
    if not res:
        raise HTTPException(status_code=404,detail='file not found')
    return res

@app.post('/files/{file_id}/extract')
def extract_file(file_id:int):
    file = get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404,detail='file not found')
    file_path = file.filepath
    extracted_text = extract_text_from_pdf(file_path)
        
    if not extracted_text:
        return {
            "status": "no_text_extracted",
            "file_id": file_id,
            "note": "File has no extractable text. Likely scanned PDF or image. OCR fallback coming soon."
        }
    update_extracted_text(file_id , extracted_text)
    return {
        "status":"extracted",
        "file_id":file_id,
        "length":len(extracted_text),
        "preview":extracted_text[:200]
    }