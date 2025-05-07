from flask import Flask, request, render_template_string
import subprocess, tempfile, os, re, joblib


# Load the pre-trained vectorizer and model at startup
vectorizer, model = joblib.load('bug_model.pkl')

# Hard‑coded suggestions for common javac errors
FALLBACK = {
    "';' expected": "Add the missing semicolon at the end of the statement.",
    "cannot find symbol": "Check for typos or missing imports or misspelled identifiers.",
    "missing return type": "Declare a return type (e.g., void) before the method name.",
    "class, interface, or enum expected": "Ensure your braces and class/interface declaration are correct.",
    "illegal start of type": "Remove stray characters or move the code inside a method or class body.",
    "cannot resolve symbol": "Verify that the variable or method name is correct and imported.",
    "variable might not have been initialized": "Ensure the variable is assigned a value on all code paths before use.",
    "incomparable types": "Use equals() or ensure both sides of == are primitive types.",
    "array required but": "You tried to index a non-array—change the variable to an array or use a different type.",
    "incompatible types": "Cast or change the type so that the assignment matches.",
    "reached end of file while parsing": "Add the missing closing brace '}'.",
    "package does not exist": "Check your import statement or package declaration for typos.",
    "method does not override or implement a method from a supertype": "Remove @Override or fix the signature.",
    "enum constant must be an identifier": "Rename your enum constant so it’s a valid Java identifier.",
    "array dimension missing": "Specify the array size like new Type[size] or correct your brackets.",
    "illegal character": "Remove or replace the invalid character—verify your file encoding is UTF-8.",
    "duplicate class": "Ensure only one public class per file and the filename matches the class name.",
    "modifier not allowed here": "Use modifiers (public, static, etc.) only in valid locations.",
    "cannot inherit from final": "You tried to extend a final class—remove the extends or change the class.",
    "<identifier> expected": "Use a valid identifier (letters, digits, _, $), not a keyword.",
    "unexpected type": "Check you’re not using an array as a variable type incorrectly.",
    "missing method body": "Add method implementation or mark the method abstract.",
    "variable .* is already defined": "Rename the duplicate variable in the same scope.",
    "catch or finally expected": "Add a catch or finally block after the try.",
    "annotation type required": "Define annotations using @interface, not @class or @interface.",
    "missing return statement": "Ensure all code paths return a value when method has non-void return.",
    "unclosed string literal": "Terminate your string literal with a closing quote.",
    "octal escape sequence": "Fix your escape sequence; Java uses \\uXXXX or \\n for newlines.",
    "')' expected": "Add the missing closing parenthesis in your expression.",
    "illegal escape character": "Use a valid escape sequence like \\n, \\t, or Unicode \\uXXXX.",
    "reached end of file in comment": "Close your comment (*/) before the end of file.",
    "invalid method declaration; return type required": "Add a return type to your method declaration.",
    "unreachable statement": "Remove or refactor code after return/break that can never be run.",
    "missing package statement": "If you’re using packages, add `package your.pkg.name;` at top.",
    "bad operand type for unary operator": "Unary operators (like !) require boolean operands.",
    "bad operand type for binary operator": "Check that the operator is used on compatible types.",
    "bad source value": "Use a valid source version for -source (e.g., 1.8, 11).",
    "bootstrap class path not set": "Specify -bootclasspath when cross‑compiling to older Java versions.",
    "already defined in class": "Rename or remove one of the duplicate method definitions so each signature is unique.",
    "else without if": "Add or move the closing brace ‘}’ before the else to match the if."




}

app = Flask(__name__)

# HTML Template
template = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Java Bug Analyzer</title>
  <style>
    body {
      font-family: 'Segoe UI', sans-serif;
      background-color: #f8f9fa;
      margin: 0;
      padding: 0;
    }
    .container {
      max-width: 960px;
      margin: 40px auto;
      background: #fff;
      padding: 30px 40px;
      border-radius: 10px;
      box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    h1 {
      color: #343a40;
      text-align: center;
      margin-bottom: 30px;
    }
    textarea {
      width: 100%;
      padding: 12px;
      border: 1px solid #ced4da;
      border-radius: 6px;
      resize: vertical;
      font-family: monospace;
      font-size: 14px;
    }
    input[type="file"] {
      margin-top: 12px;
    }
    button {
      background-color: #007bff;
      color: white;
      padding: 10px 20px;
      margin-top: 16px;
      border: none;
      border-radius: 5px;
      font-size: 16px;
      cursor: pointer;
    }
    button:hover {
      background-color: #0056b3;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 30px;
    }
    th, td {
      border: 1px solid #dee2e6;
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      background-color: #e9ecef;
      font-weight: bold;
    }
    p {
      font-size: 15px;
    }
    .footer {
      margin-top: 20px;
      font-size: 14px;
      color: #6c757d;
      text-align: right;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Java Bug Localization System</h1>
    <form method="post" enctype="multipart/form-data">
      <label for="code"><strong>Paste your Java code:</strong></label>
      <textarea name="code" rows="12" placeholder="Paste Java code here..."></textarea><br>
      <label for="file"><strong>or Upload a .java file:</strong></label><br>
      <input type="file" name="file"><br>
      <button type="submit" name="action" value="analyze">Analyze Code</button>
    </form>

    {% if result %}
      <hr>
      <h2>Analysis Results</h2>
      {% if result.errors %}
        <table>
          <tr>
            <th>Line</th>
            <th>Error Message</th>
            <th>Suggestion</th>
          </tr>
          {% for err in result.errors %}
          <tr>
            <td>{{ err.line }}</td>
            <td>{{ err.message }}</td>
            <td>{{ err.suggestion }}</td>
          </tr>
          {% endfor %}
        </table>
      {% else %}
        <p><strong>Message:</strong> {{ result.message }}</p>
        <p><strong>Suggestion:</strong> {{ result.suggestion }}</p>
      {% endif %}
      <div class="footer">
        <p><strong>Time Complexity:</strong> {{ result.time_complexity }}</p>
        <p><strong>Space Complexity:</strong> {{ result.space_complexity }}</p>
      </div>
    {% endif %}
  </div>
</body>
</html>'''


def analyze_code(code: str) -> dict:
    original = code.splitlines()
    errors = []
    patched = original.copy()
    seen = set()

    # Try up to 10 compile errors
    for _ in range(10):
        with tempfile.NamedTemporaryFile(
            suffix='.java', delete=False, mode='w', encoding='utf-8'
        ) as tmp:
            tmp.write("\n".join(patched))
            fname = tmp.name

        try:
            proc = subprocess.Popen(
                ['javac', '-Xmaxerrs', '100', fname],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            _, stderr = proc.communicate()
        except FileNotFoundError:
            os.remove(fname)
            return {
                'errors': [],
                'message': 'javac not found. Ensure JDK is installed and in your PATH.',
                'suggestion': 'Install the JDK and add its bin directory to the PATH environment variable.',
                'time_complexity': '-', 'space_complexity': '-'
            }

        os.remove(fname)
        err_str = stderr.decode().strip()
        if not err_str:
            break

        m = re.search(r'^(.*?\.java):(\d+): (.+)$', err_str, re.MULTILINE)
        if not m:
            break

        line_no = int(m.group(2))
        msg = m.group(3).strip()
        if (line_no, msg) in seen:
            break
        seen.add((line_no, msg))

        # Normalize error message for case-insensitive partial fallback matching
        normalized_msg = msg.lower().strip()
        if normalized_msg.startswith('error:'):
            normalized_msg = normalized_msg[6:].strip()

        # Try fallback dictionary match
        suggestion = None
        for pat, fix in FALLBACK.items():
            if pat.lower() in normalized_msg:
                suggestion = fix
                break

        # If no fallback match, try ML model or use default message
        if suggestion is None:
            try:
                X_vec = vectorizer.transform([msg])
                suggestion = model.predict(X_vec)[0]
            except Exception:
                suggestion = "No suggestion available. Please check the error manually or refer to the Java documentation."

        errors.append({
            'line': line_no,
            'message': msg,
            'suggestion': suggestion
        })

        # Try to patch and continue if it's a missing semicolon
        if "';' expected" in msg:
            idx = line_no - 1
            if idx < len(patched) and not patched[idx].strip().endswith(";"):
                patched[idx] += ";"
            continue

        break

    return {
        'errors': errors,
        'time_complexity': estimate_time_complexity(code),
        'space_complexity': estimate_space_complexity(code)
    }


def estimate_time_complexity(code: str) -> str:
    max_depth = 0
    stack = []
    for ln in code.splitlines():
        if re.search(r'\b(for|while)\b', ln):
            stack.append('{')
            max_depth = max(max_depth, len(stack))
        if '}' in ln and stack:
            stack.pop()
    if max_depth >= 3: return 'O(n^3)'
    if max_depth == 2: return 'O(n^2)'
    if max_depth == 1: return 'O(n)'
    return 'O(1)'

def estimate_space_complexity(code: str) -> str:
    allocs = len(re.findall(r'\bnew\b', code))
    return 'O(n)' if allocs > 1 else 'O(1)'

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST' and request.form.get('action') == 'analyze':
        code = request.form.get('code', '')
        if not code and 'file' in request.files:
            code = request.files['file'].read().decode('utf-8')
        result = analyze_code(code)
    return render_template_string(template, result=result)

if __name__ == '__main__':
    app.run(debug=True)
