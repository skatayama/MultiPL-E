# This script translates problems from the OpenAI HumanEval dataset into Haskell.
import re
import ast
from typing import List

# Make sure that there are no Optionals in exprs. Isn't there something like any in Haskell?
def check_no_Optional(exprs: List[ast.expr]):
    for e in exprs:
        match e:
            case ast.Subscript(ast.Name("Optional"), _slice, _ctx):
                raise Exception(f"Optional {e} found in Tuple")

# Adapted from humaneval_to_ocaml.py, though it caused some errors.
def translate_type(t: ast.expr) -> str:
    global needs_hashmap
    match t:
        case ast.Subscript(ast.Name(id), slice, ctx):
            match id:
                case "List":
                    return f"[{translate_type(slice)}]"
                case "Union":
                    raise Exception("Haskell does not have untagged unions.")
                case "Tuple":
                    match slice:
                        case ast.Tuple(elts, _ctx):
                            check_no_Optional(elts)
                            tys = [translate_type(elem) for elem in elts]
                            return "(" + " , ".join(tys) + ")"
                        case other:
                            raise Exception(f"Bad tuple: {slice}")
                case "Dict":
                    match slice:
                        case ast.Tuple([ast.Name(k), ast.Name(v)], _ctx):
                            key, value = translate_type(ast.Name(k)), translate_type(ast.Name(v))
                            needs_hashmap = True
                            return f"[({key}, {value})]"                          # should be a hashmap?
                        case other:
                            raise Exception(f"Bad dict: {slice}")
                case "Optional":
                    return "Maybe (" + translate_type(slice) + ")"
                case other:
                    raise Exception(f"Bad generic {other}")
        case ast.Name("int"):
            return "Int"
        case ast.Name("float"):
            return "Double"
        case ast.Name("bool"):
            return "Bool"
        case ast.Name("str"):
            return "String"
        case None:
            raise Exception("implicitly untyped argument")
        case ast.Name("Any"):
            raise Exception("Haskell does not have Any type")
        case ast.Name(x):
            raise Exception(f"unknown name {x}")
        case ast.Constant(Ellipsis):
            raise Exception("no ellipsis!!")
        case _other:
            raise Exception(f"unknown annotation: {t}")

def coerce(expr: str, type) -> str: 
    def coerce_to_option(expr: str) -> str:
        if expr == "None":
            return "Nothing"
        else:
            return f"Just ({expr})"
    match expr, type:
        case expr, ast.Subscript(ast.Name("Optional"), _):
            return coerce_to_option(expr)
        case _:
            return expr

        
# add 0 if the float starts or ends with a decimal point
def fix_float(s: str) -> str:
    if s.startswith("."):
        return "0" + s
    if s.endswith("."):
        return s + "0"
    return s


keywords = ["if", "then", "else", "let", "in", "do", "mdu", "rec", "import", "module", "type", "class", "instance", "data", "newtype", "where", "case", "of", "forall", "as", "qualified", "hiding", "deriving", "family", "default", "infix", "infixr", "infixl", "foreign", "proc"]
            
class Translator:
    stop = [ "\n\n\n" ]

    def file_ext(self) -> str:
        return "hs"

    def translate_prompt(self, name: str, args: List[ast.arg], returns: ast.expr, description: str) -> str:
        self.type = [[arg.annotation for arg in args], returns]
        return ("-- " + ('\n-- '.join(description.split('\n'))) + f"\n{name} :: {' -> '.join([translate_type(arg.annotation) for arg in args])} -> {translate_type(returns)}\n{name} =")
# all necessary imports (such as HashMap) need to be prefixed here.

    def gen_literal(self, c: bool | str | int | float | None) -> str:
        if type(c) == float:
            return fix_float(repr(c))
        if type(c) == str:
            return '"'+c.replace("\n","\\n").replace('"','\\"')+'"'
        if type(c) == int:
            return repr(c)
        if type(c) == None:
            return "Nothing"
        return repr(c)
    
    def gen_var(self, v: str) -> str:
        if v in keywords:
            return v+"'"
        return v
    def gen_list(self, elements: List[str]) -> str:
        return f"[{', '.join(elements)}]"
    def gen_tuple(self, elements: List[str]) -> str:
        return f"({', '.join(elements)})"
    def gen_dict(self, keys, values) -> str:
        return f"[{', '.join([f'({k}, {v})' for k, v in zip(keys, values)])}]"

    def gen_call(self, func:str, args: List[str]) -> str:  # I assume this is used only for unit tests and thus the function is not nullary.
        if func == "candidate":
            args = [coerce(arg, self.type[0][i]) for i, arg in enumerate(args)]
        return f"{func} ({') ('.join(args)})"

    def test_suite_prefix_lines(self, entry_point: str) -> List[str]:
        return [ f"main = check {entry_point}", f"check candidate = if (True" ]
    def test_suite_suffix_lines(self) -> List[str]:
        return [ f"  ) then putStrLn \"OK\" else error \"FAIL\""]
    def deep_equality(self, left: str, right: str) -> str:
        return f"   && {left} == {right}"

    def finalize(self, result, context) -> str:
        match context:
            case "lhs":
                return result
            case "rhs":
                return coerce(result, self.type[1])
            case _other:
                raise Exception("bad context to finalize")

