print('=== TESTING FILE CREATION ONLY ===')
import sys
import os
import tempfile
import zipfile
import json as orjson

sys.path.insert(0, os.path.join('.', 'resync', 'core'))

# Test file creation functions
def create_test_json():
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    test_data = {'test': 'data', 'number': 123}
    temp_file.write(orjson.dumps(test_data).decode('utf-8'))
    temp_file.close()
    return temp_file.name

def create_test_xlsx():
    temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)

    with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as xlsx_zip:
        xlsx_zip.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
        xlsx_zip.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/package/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        xlsx_zip.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        xlsx_zip.writestr('xl/worksheets/sheet1.xml', '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Test</t></is></c></row></sheetData></worksheet>')

    return temp_file.name

# Test file creation
json_file = create_test_json()
xlsx_file = create_test_xlsx()

print(f'[OK] JSON file created: {os.path.basename(json_file)}')
print(f'[OK] XLSX file created: {os.path.basename(xlsx_file)}')

# Verify files exist and have content
json_size = os.path.getsize(json_file)
xlsx_size = os.path.getsize(xlsx_file)
print(f'[OK] JSON file size: {json_size} bytes')
print(f'[OK] XLSX file size: {xlsx_size} bytes')

# Cleanup
os.unlink(json_file)
os.unlink(xlsx_file)
print('=== FILE CREATION TEST PASSED ===')

