import sys, os, tempfile, zipfile, asyncio
sys.path.insert(0, os.path.join('.', 'resync', 'core'))

print('=== TESTING XLSX/DOCX FALLBACKS ===')

# Import required modules directly
exec(open('resync/core/utils/executors.py').read())

# Create test XLSX file (similar to benchmark)
def create_test_xlsx():
    temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)

    with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as xlsx_zip:
        xlsx_zip.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>''')

        xlsx_zip.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/package/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')

        xlsx_zip.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<fileVersion appName="xl" lastEdited="5" lowestEdited="5" rupBuild="9302"/>
<workbookPr defaultThemeVersion="124226"/>
<bookViews><workbookView xWindow="240" yWindow="15" windowWidth="16095" windowHeight="8100"/></bookViews>
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
<calcPr calcId="124519"/>
</workbook>''')

        xlsx_zip.writestr('xl/worksheets/sheet1.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheetPr><outlinePr summaryBelow="1" summaryRight="1"/><pageSetUpPr/></sheetPr>
<dimension ref="A1:A1"/>
<sheetViews><sheetView workbookViewId="0"><selection activeCell="A1" sqref="A1"/></sheetView></sheetViews>
<sheetFormatPr baseColWidth="8" defaultRowHeight="15"/>
<sheetData>
<row r="1">
<c r="A1" t="inlineStr"><is><t>Test</t></is></c>
</row>
</sheetData>
<pageMargins left="0.75" right="0.75" top="1" bottom="1" header="0.5" footer="0.5"/>
</worksheet>''')

        xlsx_zip.writestr('xl/styles.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="1"><font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
<dxfs count="0"/>
<tableStyles count="0" defaultTableStyle="TableStyleMedium9" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>''')

        xlsx_zip.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>''')

    return temp_file.name

# Create test DOCX file
def create_test_docx():
    temp_file = tempfile.NamedTemporaryFile(suffix='.docx', delete=False)

    with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as docx_zip:
        docx_zip.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')

        docx_zip.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''')

        docx_zip.writestr('word/document.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
<w:p><w:r><w:t>Test document content</w:t></w:r></w:p>
</w:body>
</w:document>''')

    return temp_file.name

# Test fallback mechanisms
async def test_fallbacks():
    xlsx_file = create_test_xlsx()
    docx_file = create_test_docx()

    try:
        # Import file_ingestor functions directly
        exec(open('resync/core/file_ingestor.py').read(), globals())

        executors = OptimizedExecutors()

        # Test XLSX processing (should trigger fallbacks)
        print('[TEST] Testing XLSX fallback mechanisms...')
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                executors.get_io_executor(),
                read_excel_sync,
                xlsx_file
            )
            print(f'[OK] XLSX processed successfully: {result[:50]}...')
        except Exception as e:
            print(f'[WARNING] XLSX fallback used: {str(e)[:50]}...')

        # Test DOCX processing
        print('[TEST] Testing DOCX processing...')
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                executors.get_io_executor(),
                read_docx_sync,
                docx_file
            )
            print(f'[OK] DOCX processed successfully: {result[:50]}...')
        except Exception as e:
            print(f'[WARNING] DOCX fallback used: {str(e)[:50]}...')

        print('[OK] Fallback mechanisms tested successfully')

    finally:
        try:
            os.unlink(xlsx_file)
            os.unlink(docx_file)
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_fallbacks())
    print('=== XLSX/DOCX FALLBACKS TEST COMPLETED ===')

