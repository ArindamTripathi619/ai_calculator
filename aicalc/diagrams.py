# ...existing diagrams.py code...
import os
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
import uuid
import tempfile
import subprocess
from aicalc.config import logger

def generate_matplotlib_diagram(python_code, output_filename):
    try:
        plt.figure(figsize=(8, 6), dpi=100)
        plt.style.use('default')
        safe_globals = {
            'plt': plt,
            'np': np,
            'numpy': np,
            'matplotlib': matplotlib,
            'nx': nx,
            'networkx': nx,
            'sin': np.sin,
            'cos': np.cos,
            'tan': np.tan,
            'log': np.log,
            'exp': np.exp,
            'sqrt': np.sqrt,
            'pi': np.pi,
            'e': np.e,
            'linspace': np.linspace,
            'arange': np.arange,
            'array': np.array,
            'range': range,
            'len': len,
            'abs': abs,
            'max': max,
            'min': min,
            'python': None,
        }
        exec(python_code, safe_globals)
        output_path = os.path.join('static', 'generated', output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close()
        return output_filename
    except Exception as e:
        logger.error(f"Error generating matplotlib diagram: {str(e)}")
        plt.close()
        return None

def generate_tikz_diagram(tikz_code, output_filename):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            cleaned_tikz_code = tikz_code.strip()
            cleaned_tikz_code = re.sub(r'(?<!\\)\$', r'\\$', cleaned_tikz_code)
            lines = cleaned_tikz_code.split('\n')
            tikz_lines = []
            inside_tikzpicture = False
            for line in lines:
                line_stripped = line.strip()
                if (line_stripped.startswith('\\documentclass') or
                    line_stripped.startswith('\\usepackage') or 
                    line_stripped.startswith('\\usetikzlibrary') or
                    line_stripped.startswith('\\pgfplotsset') or
                    line_stripped == '\\begin{document}' or
                    line_stripped == '\\end{document}'):
                    continue
                if line_stripped.startswith('\\begin{tikzpicture}'):
                    inside_tikzpicture = True
                    continue
                elif line_stripped == '\\end{tikzpicture}':
                    inside_tikzpicture = False
                    continue
                elif inside_tikzpicture or not any(x in line_stripped for x in ['\\documentclass', '\\begin{document}', '\\end{document}']):
                    tikz_lines.append(line)
            cleaned_tikz_code = '\n'.join(tikz_lines).strip()
            if 'binary tree' in tikz_code.lower() or 'tree' in tikz_code.lower() or 'wide' in tikz_code.lower():
                cleaned_tikz_code = f"% Explicit bounding box for wide diagrams\n\\path[use as bounding box] (-12,-8) rectangle (12,6);\n{cleaned_tikz_code}"
            logger.info(f"Processing TikZ code: {cleaned_tikz_code[:200]}...")
            latex_content = f"""
\\documentclass[border=30pt]{{standalone}}
\\usepackage{{tikz}}
\\usepackage{{pgfplots}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usetikzlibrary{{arrows,automata,positioning,shapes,patterns,decorations.pathreplacing,calc,angles,quotes,trees}}
\\pgfplotsset{{compat=1.18}}

\\begin{{document}}
\\begin{{tikzpicture}}[auto,node distance=2cm,>=stealth']
{cleaned_tikz_code}
\\end{{tikzpicture}}
\\end{{document}}
"""
            tex_file = os.path.join(temp_dir, 'diagram.tex')
            with open(tex_file, 'w') as f:
                f.write(latex_content)
            try:
                result = subprocess.run([
                    'pdflatex', 
                    '-interaction=nonstopmode',
                    '-output-directory', temp_dir,
                    tex_file
                ], capture_output=True, text=True, timeout=30)
                pdf_file = os.path.join(temp_dir, 'diagram.pdf')
                if result.returncode != 0:
                    logger.error(f"pdflatex failed with return code {result.returncode}")
                    logger.error(f"LaTeX content that failed:")
                    logger.error(latex_content)
                    if result.stdout:
                        logger.error(f"pdflatex stdout: {result.stdout[-500:]}")
                    if result.stderr:
                        logger.error(f"pdflatex stderr: {result.stderr}")
                    return None
                if not os.path.exists(pdf_file):
                    logger.error("PDF file was not generated despite successful compilation")
                    return None
                output_path = os.path.join('static', 'generated', 'tikz', output_filename)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                try:
                    result = subprocess.run([
                        'pdftoppm',
                        '-png',
                        '-singlefile',
                        '-r', '300',
                        pdf_file,
                        output_path.replace('.png', '')
                    ], capture_output=True, text=True, timeout=15)
                    if result.returncode != 0:
                        logger.error(f"pdftoppm failed with return code {result.returncode}")
                        if result.stderr:
                            logger.error(f"pdftoppm stderr: {result.stderr}")
                        raise subprocess.CalledProcessError(result.returncode, 'pdftoppm')
                    return f"tikz/{output_filename}"
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    logger.warning(f"pdftoppm failed: {e}, trying ImageMagick convert...")
                    try:
                        result = subprocess.run([
                            'convert',
                            '-density', '300',
                            '-quality', '100',
                            pdf_file,
                            output_path
                        ], capture_output=True, text=True, timeout=15)
                        if result.returncode != 0:
                            logger.error(f"ImageMagick convert failed with return code {result.returncode}")
                            if result.stderr:
                                logger.error(f"convert stderr: {result.stderr}")
                            return None
                        return f"tikz/{output_filename}"
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        logger.error(f"ImageMagick convert also failed: {e}")
                        logger.error("Neither pdftoppm nor ImageMagick convert available for PDF conversion")
                        return None
            except subprocess.TimeoutExpired:
                logger.error("TikZ compilation timed out")
                return None
            except subprocess.CalledProcessError as e:
                logger.error(f"TikZ compilation failed with return code {e.returncode}")
                if e.stdout:
                    logger.error(f"TikZ stdout: {e.stdout}")
                if e.stderr:
                    logger.error(f"TikZ stderr: {e.stderr}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error during TikZ compilation: {str(e)}")
                return None
    except Exception as e:
        logger.error(f"Error generating TikZ diagram: {str(e)}")
        return None
