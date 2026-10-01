"""Development-only: typeset response_to_reviewers.md as a PDF (the machine has no pandoc). Handles the subset of
Markdown the letter uses: # and ## headings, **bold**, *italic*, `code`, bullet lists, and paragraphs."""
import re, os, subprocess, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); src = os.path.join(HERE, '..', 'response_to_reviewers.md'); md = open(src).read()
def esc(t):
    t = t.replace('\\', r'\textbackslash{}').replace('%', r'\%').replace('#', r'\#').replace('&', r'\&').replace('_', r'\_').replace('$', r'\$').replace('–', '--')
    t = re.sub(r'`([^`]*)`', r'\\texttt{\1}', t); t = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', t); t = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'\\emph{\1}', t)
    return re.sub(r'"([^"]*)"', r"``\1''", t)
body = []; in_list = False
for line in md.split('\n'):
    if line.startswith('- '):
        if not in_list: body.append(r'\begin{itemize}\setlength{\itemsep}{2pt}'); in_list = True
        body.append(r'\item ' + esc(line[2:])); continue
    if in_list: body.append(r'\end{itemize}'); in_list = False
    if line.startswith('## '): body.append(r'\section*{' + esc(line[3:]) + '}')
    elif line.startswith('# '): body.append(r'\begin{center}\Large\textbf{' + esc(line[2:]) + r'}\end{center}')
    else: body.append(esc(line))
if in_list: body.append(r'\end{itemize}')
tex = r'''\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}\usepackage[T1]{fontenc}\usepackage{lmodern}\usepackage{microtype}\usepackage{parskip}
\usepackage[hidelinks,pdfauthor={Anonymous},pdftitle={Response to Reviewers, submission 127}]{hyperref}
\begin{document}
''' + '\n'.join(body) + '\n\\end{document}\n'
d = tempfile.mkdtemp(); open(os.path.join(d, 'letter.tex'), 'w').write(tex)
for _ in range(2): r = subprocess.run(['pdflatex', '-interaction=nonstopmode', 'letter.tex'], cwd=d, capture_output=True, text=True)
out = os.path.join(HERE, '..', 'response_to_reviewers.pdf'); shutil.copy(os.path.join(d, 'letter.pdf'), out); print('wrote', os.path.relpath(out), '| latex errors:', r.stdout.count('\n!'))
