import os

file1 = r'd:\LLM_mini\DESIGN(1).md'
file2 = r'd:\LLM_mini\DESIGN.md'

with open(file1, 'r', encoding='utf-8') as f:
    lines_1 = f.readlines()

with open(file2, 'r', encoding='utf-8') as f:
    lines_2 = f.readlines()

tree_start_idx = 0
for i, line in enumerate(lines_2):
    if line.startswith('## 📂 Cấu Trúc'):
        tree_start_idx = i + 1
        break
tree_content = "".join(lines_2[tree_start_idx:]).strip()

out_lines = []
i = 0
while i < len(lines_1):
    line = lines_1[i]
    out_lines.append(line)
    if line.startswith('## 16. Cấu Trúc Thư Mục Dự Án'):
        out_lines.append('\n' + tree_content + '\n\n')
        i += 1
        while i < len(lines_1) and not lines_1[i].startswith('## 17.'):
            i += 1
        continue
    i += 1

with open(file2, 'w', encoding='utf-8') as f:
    f.writelines(out_lines)

os.remove(file1)
print("Merge complete!")
