import json

with open('analysis_reports/pyright_baseline_report.json', 'r') as f:
    data = json.load(f)

missing_imports = []
for diag in data['generalDiagnostics']:
    if diag.get('rule') == 'reportMissingImports':
        missing_imports.append({
            'file': diag['file'].replace('d:\\Python\\GITHUB\\hwa-new-main-final\\', ''),
            'message': diag['message'],
            'line': diag['range']['start']['line']
        })

print(f'Total missing import errors: {len(missing_imports)}')
print('\nTop 30 missing import errors:')
for i, imp in enumerate(missing_imports[:30], 1):
    print(f'{i:2d}. {imp["file"]}:{imp["line"]} - {imp["message"]}')
