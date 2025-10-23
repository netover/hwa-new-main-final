import json

# Read the radon report JSON file
with open('radon_report.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extract functions with complexity C and D
c_and_d_functions = []

for file, functions in data.items():
    for func in functions:
        if func['rank'] == 'C' or func['rank'] == 'D':
            c_and_d_functions.append({
                'file': file,
                'name': func['name'],
                'rank': func['rank'],
                'complexity': func['complexity'],
                'lineno': func['lineno']
            })

# Sort by complexity (highest first)
c_and_d_functions.sort(key=lambda x: x['complexity'], reverse=True)

# Print results
print(f"Found {len(c_and_d_functions)} functions with complexity C or D:\n")
for func in c_and_d_functions:
    print(f"{func['file']}: {func['name']} ({func['rank']}, {func['complexity']}) at line {func['lineno']}")

# Print summary
print(f"\nSummary:")
print(f"- Functions with complexity D: {len([f for f in c_and_d_functions if f['rank'] == 'D'])}")
print(f"- Functions with complexity C: {len([f for f in c_and_d_functions if f['rank'] == 'C'])}")
print(f"- Highest complexity: {c_and_d_functions[0]['complexity'] if c_and_d_functions else 0}")