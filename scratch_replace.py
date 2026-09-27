import os
import glob
import re

files = glob.glob('src/**/*.py', recursive=True)
for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We want to find:
    # templates.TemplateResponse(
    #     "filename.html",
    #     context_dict
    # )
    # And replace with:
    # templates.TemplateResponse(
    #     request=request,
    #     name="filename.html",
    #     context=context_dict
    # )
    
    # Let's do it with regex
    # Match templates.TemplateResponse( \s* "(.+?)" \s*, \s* (.*?) )
    # But it can be multi-line
    
    new_content = re.sub(
        r'templates\.TemplateResponse\(\s*("[\w/.]+")\s*,',
        r'templates.TemplateResponse(request=request, name=\1, context=',
        content
    )
    # the main.py error html has:
    # return templates.TemplateResponse(
    #     "error.html",
    #     {"request": request, ...},
    #     status_code=exc.status_code,
    # )
    
    if new_content != content:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {file}")
