import sys
import re
import ctypes


variables = {}

def replace_var(text):
    parts = re.split(r'(\$[a-zA-Z_][a-zA-Z0-9_]*\$)', text)
    result = ''
    for part in parts:
        if re.fullmatch(r'\$[a-zA-Z_][a-zA-Z0-9_]*\$', part):
            var_name = part[1:-1]
            val = variables.get(var_name, f"<{var_name}?>")
            result += str(val)
        else:
            result += part.replace('"', '')
    return result

def remove_comments(code):
    lines = code.split('\n')
    return '\n'.join(line.split('//')[0] for line in lines)

# Extended safe_eval to support comparison operators
def safe_eval(expr):
    # Autorise chiffres, opérateurs arithmétiques et comparaisons simples
    allowed = re.match(r'^[0-9+\-*/().<>=! \t]+$', expr)
    if allowed:
        try:
            return str(eval(expr))
        except:
            return "<Erreur calcul>"
    return "<Calcul non autorisé>"

def parse_list_elements(content):
    return [e.strip().strip("'") for e in content.split(';') if e.strip()]

def interpreter(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    code = remove_comments(code)

    pattern_all = r'''(
        set\.[^/]+/.*?/
        |set/\$[a-zA-Z_][a-zA-Z0-9_]*\$/ 
        |set/\(.*?\)(::[a-zA-Z_][a-zA-Z0-9_]*::)?/
        |int\.set/\(.*?\)(::[a-zA-Z_][a-zA-Z0-9_]*::)?/
        |\[::[a-zA-Z_][a-zA-Z0-9_]*::/.*?/\]
        |_int\.\[::[a-zA-Z_][a-zA-Z0-9_]*::/.*?/\]
        |set/\{\$[a-zA-Z_][a-zA-Z0-9_]*\$\:.*?\}/
        |set/\{\$[a-zA-Z_][a-zA-Z0-9_]*\$\:.*?\}::[a-zA-Z_][a-zA-Z0-9_]*::/
        |<if>\(.*?\)/.*?/
        |<elif>\(.*?\)/.*?/
        |<else>/.*?/
    )'''

    instructions = re.findall(pattern_all, code, re.VERBOSE)
    instructions = [instr[0] if isinstance(instr, tuple) else instr for instr in instructions]

    condition_met = False  # Pour gérer <if>/<elif>/<else> chain

    for instr in instructions:
        instr = instr.strip()

        # Gestion conditions
        if instr.startswith("<if>"):
            # Extrait condition et instruction
            m = re.match(r'<if>\((.*?)\)/(.*)/', instr)
            if m:
                cond_expr, cmd = m.groups()
                cond_val = safe_eval(replace_var(cond_expr))
                if cond_val == "True" or cond_val == "1":
                    condition_met = True
                    # Exécute la commande sous condition
                    # On réutilise le traitement classique en simulant set.show etc.
                    process_instruction(cmd.strip(), variables)
                else:
                    condition_met = False
            continue

        if instr.startswith("<elif>"):
            m = re.match(r'<elif>\((.*?)\)/(.*)/', instr)
            if m:
                if condition_met:
                    # Condition déjà vraie dans if/elif précédent : ignore ce elif
                    continue
                cond_expr, cmd = m.groups()
                cond_val = safe_eval(replace_var(cond_expr))
                if cond_val == "True" or cond_val == "1":
                    condition_met = True
                    process_instruction(cmd.strip(), variables)
                else:
                    condition_met = False
            continue

        if instr.startswith("<else>"):
            m = re.match(r'<else>/(.*)/', instr)
            if m:
                if not condition_met:
                    # Si aucune condition if/elif précédente vraie, execute else
                    cmd = m.group(1)
                    process_instruction(cmd.strip(), variables)
                # Reset pour prochaine série
                condition_met = False
            continue

        # Sinon instructions classiques
        process_instruction(instr, variables)


def process_instruction(instr, variables):
    instr = instr.strip()

    # set.show/"Texte"
    if instr.startswith("set.show/"):
        content = instr[len("set.show/"):-1]
        output = replace_var(content)
        print(output)

    # set.input/"prompt"::var::
    elif instr.startswith("set.input/"):
        m = re.match(r'set\.input/"([^"]*)"::([a-zA-Z_][a-zA-Z0-9_]*)::/', instr)
        if m:
            prompt, var = m.groups()
            variables[var] = input(prompt + " ")

    # set/$var$ (affiche variable)
    elif instr.startswith("set/$"):
        m = re.match(r'set/\$([a-zA-Z_][a-zA-Z0-9_]*)\$/', instr)
        if m:
            varname = m.group(1)
            val = variables.get(varname, f"<{varname}?>")
            if isinstance(val, list):
                print(', '.join(map(str, val)))
            else:
                print(val)

    # set/(expr)
    elif instr.startswith("set/("):
        m = re.match(r'set/\((.*?)\)(::([a-zA-Z_][a-zA-Z0-9_]*?)::)?/', instr)
        if m:
            expr, _, var = m.groups()
            result = safe_eval(replace_var(expr))
            if var:
                variables[var] = result
            else:
                print(result)

    # int.set/(expr)
    elif instr.startswith("int.set/("):
        m = re.match(r'int\.set/\((.*?)\)(::([a-zA-Z_][a-zA-Z0-9_]*)::)?/', instr)
        if m:
            expr, _, var = m.groups()
            result = safe_eval(replace_var(expr))
            if var:
                variables[var] = result
            else:
                print(result)
        # set.alert/"Texte d'alerte"/
    elif instr.startswith("set.alert/"):
        m = re.match(r'set\.alert/"([^"]*)"/', instr)
        if m:
            message = replace_var(m.group(1))
            # Utilise une boîte de dialogue Windows
            ctypes.windll.user32.MessageBoxW(0, message, "Alerte:cesar", 0x40 | 0x1)


    # [::var::/'el1'; 'el2'/]
    elif instr.startswith("[::"):
        m = re.match(r'\[::([a-zA-Z_][a-zA-Z0-9_]*)::/(.*?)/\]', instr)
        if m:
            var, content = m.groups()
            variables[var] = [e.strip().strip("'") for e in content.split(';') if e.strip()]

    # _int.[::var::/'1'; '2'/]
    elif instr.startswith("_int.[::"):
        m = re.match(r'_int\.\[::([a-zA-Z_][a-zA-Z0-9_]*)::/(.*?)/\]', instr)
        if m:
            var, content = m.groups()
            try:
                variables[var] = [int(e.strip().strip("'")) for e in content.split(';') if e.strip()]
            except ValueError:
                print(f"<Erreur liste int pour {var}>")

    # set/{$var$:[indices]}
    elif instr.startswith("set/{$"):
        m = re.match(r'set/\{\$([a-zA-Z_][a-zA-Z0-9_]*)\$\:((?:\s*\[\d+\];?)*)\}/', instr)
        if m:
            list_var, indices_part = m.groups()
            indices = re.findall(r'\[(\d+)\]', indices_part)
            lst = variables.get(list_var, [])
            output = []
            for i in indices:
                try:
                    output.append(str(lst[int(i)]))
                except:
                    output.append(f"<Erreur indice {i}>")
            print(" ".join(output))

        m2 = re.match(r'set/\{\$([a-zA-Z_][a-zA-Z0-9_]*)\$\:((?:\s*\[\d+\];?)*)\}::([a-zA-Z_][a-zA-Z0-9_]*)::/', instr)
        if m2:
            list_var, indices_part, new_var = m2.groups()
            indices = re.findall(r'\[(\d+)\]', indices_part)
            lst = variables.get(list_var, [])
            output = []
            for i in indices:
                try:
                    output.append(str(lst[int(i)]))
                except:
                    output.append(f"<Erreur indice {i}>")
            variables[new_var] = output

    else:
        pass


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python interpreter.py mon_code.cesr")
        sys.exit(1)

    filename = sys.argv[1]
    if not filename.endswith(".cesr"):
        print("Erreur : Le fichier doit avoir l'extension '.cesr'")
        sys.exit(1)

    interpreter(filename)
