import uvicorn
from app import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)


#open app automatically on start? add option to settings, start on login
#improve chat formatting
#clarity of model switching in chat, identify which section uses which model

#advertisements
#two answer columns, one with result, another with related info
#how to record people visit advertisements? without logging private info
#yellow pages? advertisement channel connecting directly to customer base
#this Wednesday taiwan time?
#used in libraries? do libraries have this funding 
#public library, university library funding? put their files in the backend for evaluation
#check if mobile can install LLM, iphone, android
#draft email regarding these topics and link peter/eric

#fixed model dropdown UI bug
#fixed ollama model detection for various systems
#add persistent chat (history, archive, settings.json)
#migrate those folders to application support for storage
#fix app icon

#add regex for format
#find a white paper template
#support skills for alfred? allows multiple tools/uses
#https://github.com/anthropics/skills/tree/main/skills/docx/scripts

#search query in settings
#ask a question, have LLM give 3-5 keywords related to question

#add where quote was found in Alfred
#use email multi delete function
