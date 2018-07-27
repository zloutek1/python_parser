from collections import namedtuple
import inspect
import functools
import re
from pprint import pprint
import textwrap


class ParseError(Exception):
    pass


class _:
    """
    decorator function that does the parser logic

    example1:
        @_("function_declaration : func function_name parameter_clause function_body")
        def parse_function_definition(self, name, parameters, body):
            return FunctionNode(name, parameters, body)

    decorator argument has to be in format:
        "function_name : arg1 arg2 arg3 ..."

    we can provide alternatives by specifiing the same function_name
    we can see alternatives in example2

    example2:
        @("parameter_clause : ( parameter_list )")
        def parse_clause(self, parameters):
            return parameters

        @("parameter_clause : ( )")
        def parse_clause1(self):
            return []

    how does it work:
        lets say that we call self.pase_clause() as a starting node
        the decorator
            looks for Node '('
            tries to call decorator with function_name of "parameter_list"
            looks for Node ')'

        if the Node was not found or the call failed a ParseError will be thrown

        when ParseError occured the decorator tries to call
        to alternative function instead; in example2 that would be "parameter_clause : ( )"

        if all alternatives fail, return 'Error' to the function above
        this is necessary because all of the decorator's work is done recursively

    types of parameters recognised:
        endpoint:
            used for Tokens such as identifier or literal
            decorator passes arguments self and value

            marked with '_' example @_("indentifier : _")

        argumentless:
            used in development of certain function as stopping point
            the function does not take any arguments

            marked with '.' example @_("function_body : .")

        autoedit:
            used as a redirect from user-defined function to a
            automatically generated function on the start of the
            program with a fix for LEFT RECURSION ERROR

            marked with 'autoedit' example @_("term : autoedit")

        method:
            redirects to some other decorator with function_name
            in example1 function will eventually call the function
                parse_clause in example2 because one of its arguments is
                parameter_clause

        operator:
            consumes and stores the math and logical operators

        ignorable:
            ignores any character non specified above
            this just asserts that the character is there, but
            does not hold any additional value later on

            for example a comma just separates two arguments,
            but is not important as an individaul argument

    result:
        after processing the recursive decorators the decorators
        calls its function (with any unique name),
        passes arguments it parsed into the function
        and returns the function's return value

        can be seen in example1

    """

    def __init__(decorator, parameters: str):
        decorator.parameters = parameters

    def __call__(decorator, func):
        func.parameters = decorator.parameters

        @functools.wraps(func)
        def wrapper(self, *args, level=0, debug=False, ** kwargs):
            parameters = func.parameters

            arguments_data = []
            arguments = inspect.getargspec(func).args[1:]
            funcName = parameters.split(" : ", 1)[0]
            startingPosition = self.executeIndex

            # getAlternatives(parameters, funcName)
            expectedPattern = parameters.split(" : ", 1)[1]
            alternatives = list(zip(self._get_patterns(funcName), self._get_methods(funcName)))
            expectedPatternIndex = list(map(lambda alt: alt[0], alternatives)).index(expectedPattern)
            alternatives = [method for pattern, method in alternatives[expectedPatternIndex + 1:]]

            params = expectedPattern.split()

            try:
                for parameter in params:

                    # parseEndpoint(parameter)
                    #
                    # endpoint is a function with just value
                    # such as identifier or literal
                    #
                    if parameter == "_":
                        if self._peek(expected_type=funcName, peekIndex=self.executeIndex):
                            retval = self._consume(expected_type=funcName, consumeIndex=self.executeIndex)
                            retval = func(self, retval)
                            arguments_data.append(retval)

                            if debug:
                                print(" " * (level * 4), f"{func.__name__} > parsing endpoint {funcName} with value {retval}")

                            return retval
                        else:
                            raise ParseError(f"endpoint: invalid pattern, got '{self._peek(peekIndex=self.executeIndex)}' expected '{parameter}'")

                    # parseArgumentless(parameter)
                    #
                    # functuion which does not take any
                    # arguemnts, just self
                    #
                    elif parameter == ".":

                        if debug:
                            print(" " * (level * 4), f"{func.__name__} > calling argumentless function {func.__name__}")

                        newkwargs = {key: value for key, value in zip(arguments, arguments_data)}
                        kwargs = {**newkwargs, **kwargs}
                        return func(self, *args, **kwargs)

                    # parseAutoedit(parameter)
                    #
                    # function which was edited by leftRecursionErrorHandler
                    #
                    elif parameter == "autoedit":

                        autoedit = list(filter(lambda fn: fn.__name__ == f"parse_{funcName}_autoedit", self._get_methods(funcName)))[0]

                        if debug:
                            print(" " * (level * 4), f"{func.__name__} > parsing autoedit {autoedit.__name__}")

                        parsed = autoedit(self, level=level + 1, debug=debug)

                        if parsed is 'Error':
                            raise ParseError(f"autoedit: recieved error")

                        if debug:
                            print(" " * (level * 4), f"{func.__name__} > autoedit returned {parsed}, now at index {self.executeIndex}")

                        arguments_data += parsed

                    # parseRecursive(parameter)
                    #
                    # if parameter is a function reference
                    # call that reference
                    #
                    elif self._is_method_avalable(parameter):

                        if debug:
                            print(" " * (level * 4), f"{func.__name__} > parsing callable {parameter}")

                        parsed = self._tryParsing(parameter, level, debug=debug)

                        if parsed is 'Error':
                            raise ParseError(f"callable: recieved error")

                        if debug:
                            print(" " * (level * 4), f"{func.__name__} > callable returned {parsed}, now at index {self.executeIndex}")

                        if parameter.endswith("_autoedit"):
                            arguments_data += parsed
                        else:
                            arguments_data.append(parsed)

                    # parseOperator(parameter)
                    #
                    #
                    elif self._peek(expected_type="operator", peekIndex=self.executeIndex):
                        if self._peek(expected_value=parameter, peekIndex=self.executeIndex):
                            op = self._consume(expected_type="operator", expected_value=parameter, consumeIndex=self.executeIndex)
                            arguments_data.append(op)

                            if debug:
                                print(" " * (level * 4), f"{func.__name__} > consumed operator {parameter}")
                        else:
                            raise ParseError(f"got wrong operator, expected {self._peek(peekIndex=self.executeIndex).value} but got {parameter}")

                    # parseIgnorableChar(parameter)
                    #
                    # ignore any non alphabetic or non numerical character
                    # except operators and others specified above
                    #
                    else:
                        if self._peek(expected_value=parameter, peekIndex=self.executeIndex):
                            if debug:
                                print(" " * (level * 4), f"{func.__name__} > parsing ignorable {parameter}")

                            self._consume(expected_value=parameter, consumeIndex=self.executeIndex)

                        else:
                            raise ParseError(f"ignorable: invalid pattern, got '{self._peek(peekIndex=self.executeIndex)}' expected '{parameter}'")

            except ParseError as e:
                if debug:
                    print(" " * (level * 4), f"[!] {func.__name__} > recieved ParseError", e)
                    print(" " * (level * 4), f"[!] {func.__name__} > backtracking from {self.executeIndex} to {startingPosition}")

                self.executeIndex = startingPosition

                # tryAlternative(alternatives)
                #
                # before returning error
                # try other alternative patterns
                #
                if len(alternatives) != 0:
                    if debug:
                        print("-" * 10)
                        print(" " * (level * 4), f"{func.__name__} > Switching to alternative")
                        print(" " * (level * 4), f"{func.__name__} > at index {self.executeIndex}")

                    altretval = alternatives[0](self, level=level, debug=debug)
                    # altretval = alternative(self, level=level, debug=debug)

                    return altretval

                return 'Error'

            newkwargs = {key: value for key, value in zip(arguments, arguments_data)}
            kwargs = {**newkwargs, **kwargs}
            retval = func(self, *args, **kwargs)

            if debug:
                print(" " * (level * 4), f"{func.__name__} > function {func.__name__} returned {retval}")

            return retval
        return wrapper


class Parser:
    tokens = []
    _decorated_methods = []

    def __init__(self, tokens):
        self.tokens = tokens
        self.executeIndex = 0

    def parse(self):
        tree = []
        # while len(self.tokens) != 0:
        tree.append(self.parse_start_of_file())
        return tree

    def __init_subclass__(cls, shouldHandleLeftRecursion=True, **kwargs):
        super().__init_subclass__(**kwargs)

        """
        if Parser shouldHandleLeftRecursion then
        detect every decorated function with first parameter same as the function_name

        example1:
            @_("statements : statements statement")
            ...

        Parser will change the function parameter into
            @_("statements : statements_autoedit")

        and will define new functions which will remove left recursion
        the rules can be seen in docs of fixLeftRecursion() function
        """

        def defineNewFunction(newFuncName, newExpectedPattern, origFunc=None):
            #
            # prepareArguments(newExpectedPattern)
            #
            if origFunc is None:
                arg_names = newExpectedPattern.split(' : ', 1)[1].split()
                arg_names = list(map(lambda arg: arg.replace('\'', ''), arg_names))
                arg_names = list(map(lambda arg: re.sub("[\+\-\*\/]", "op", arg), arg_names))
                arg_names = ", ".join(arg_names)
            else:
                arg_names = inspect.getargspec(origFunc.__wrapped__).args[1:]
                arg_names = ", ".join(arg_names)

            #
            # prepareExecutableFunction()
            #
            to_exec = ""
            to_exec += f"@_(\"{newExpectedPattern}\")\n"

            if origFunc is None:
                to_exec += f"def {newFuncName}(self, {arg_names}):\n"
                to_exec += f"    return [item for val in ({arg_names},) for item in (val if type(val) in (list, tuple) else [val])]\n"

            else:
                to_exec += '\n'.join(textwrap.dedent(inspect.getsource(origFunc)).split('\n')[1:])

            exec(to_exec)

            #
            # addFunctionToParser()
            #
            funcObj = locals()[newFuncName]
            funcName, expectedPattern = funcObj.parameters.split(' : ', 1)

            setattr(cls, newFuncName, funcObj)
            cls._decorated_methods.append((funcName, expectedPattern, funcObj))

        def fixLeftRecursion(funcName, patterns):
            """
                A -> Aα1 | Aα2 | ... | Aαm | β1 | β2 | ... | βn

                - convert to -

                A -> β1A' | β2A' | ... | βnA'
                A' -> α1A' | α2A' | ... | αmA' | ε
            """
            print("[WARNING]: Autofixing left recursion error for function", funcName)

            α = list(filter(lambda pattern: pattern.startswith(funcName), patterns))
            α = list(map(lambda pattern: pattern.split(' ', 1)[1] if ' ' in pattern else pattern, α))
            β = list(filter(lambda pattern: not pattern.startswith(funcName), patterns))

            if len(α) == 0 or len(β) == 0:
                raise ParseError(f"while attempting to parse {funcName} got left recursion error, try to provide an alternative")

            #
            # generateRule1()
            #
            for i, beta in enumerate(β):
                defineNewFunction(f"parse_{funcName}_{i+1}_autoedit" if i != 0 else f"parse_{funcName}_autoedit", f"{funcName}_autoedit : {beta} {funcName}\'")

            #
            # generateRule2And3()
            #
            for i, alpha in enumerate(α):
                defineNewFunction(f"parse_{funcName}_leftrecursion_{i+1}" if i != 0 else f"parse_{funcName}_leftrecursion", f"{funcName}\' : {alpha} {funcName}\'")
                i += 1
                defineNewFunction(f"parse_{funcName}_leftrecursion_{i+1}" if i != 0 else f"parse_{funcName}_leftrecursion", f"{funcName}\' : {alpha}")

        #
        # getAvalableFunctions()
        #
        parseFunctions = {key: value
                          for key, value in cls.__dict__.items()
                          if not key.startswith("__") and key != 'parse'}

        #
        # getAvalablePatterns(parseFunctions)
        #
        allPatterns = [func.parameters
                       for func in parseFunctions.values()]

        #
        # parseEachFunction(parseFunctions)
        #
        for origName, funcObj in parseFunctions.items():
            funcName, expectedPattern = funcObj.parameters.split(' : ', 1)
            params = expectedPattern.split()

            #
            # didLeftRecursionOccur(funcName, params)
            #
            if funcName == params[0] and shouldHandleLeftRecursion:
                delattr(cls, origName)
                defineNewFunction(origName, f"{funcName} : {funcName}_autoedit", funcObj)

                otherPatterns = list(filter(lambda pattern: pattern.startswith(funcName + " :"), allPatterns))
                otherPatterns = [pattern.split(' : ', 1)[1] for pattern in otherPatterns]
                fixLeftRecursion(funcName, otherPatterns)
            else:
                cls._decorated_methods.append((funcName, expectedPattern, funcObj))

    def _get_avalable_methods(self):
        return list(sorted(set(map(lambda method: method[0], self._decorated_methods))))

    def _is_method_avalable(self, method_name):
        return method_name in self._get_avalable_methods()

    def _get_patterns(self, withName):
        avalable_decorators = list(filter(lambda method: method[0] == withName, self._decorated_methods))
        avalable_decorators = self._sortMethods(avalable_decorators)
        return list(map(lambda method: method[1], avalable_decorators))

    def _get_methods(self, withName):
        avalable_decorators = list(filter(lambda method: method[0] == withName, self._decorated_methods))
        avalable_decorators = self._sortMethods(avalable_decorators)
        return list(map(lambda method: method[2], avalable_decorators))

    def _tryParsing(self, method_name, level, debug):
        if self._is_method_avalable(method_name):
            return self._get_methods(method_name)[0](self, level=level + 1, debug=debug)

    def _peek(self, expected_type=None, expected_value=None, peekIndex=0):
        if peekIndex >= len(self.tokens):
            return False

        if expected_type is not None:
            return self.tokens[peekIndex].type == expected_type.strip()

        if expected_value is not None:
            return self.tokens[peekIndex].value == expected_value.strip()

        return self.tokens[peekIndex]

    def _consume(self, *, expected_type=None, expected_value=None, consumeIndex=0):
        if expected_type is not None and self.tokens[consumeIndex].type == expected_type.strip():
            self.executeIndex += 1
            return self.tokens[consumeIndex].value

        if expected_value is not None and self.tokens[consumeIndex].value == expected_value.strip():
            self.executeIndex += 1
            return self.tokens[consumeIndex].value

        raise AssertionError(f"neither expected_type {expected_type} nor expected_value {expected_value} match token {self.tokens[consumeIndex]}")

    def _sortMethods(self, methods):
        output = [fn for fn in methods if 'autoedit' in fn[1]]
        output += [fn for fn in methods if fn[0] + "\'" in fn[1]]
        output += [fn for fn in methods if 'autoedit' not in fn[1] and fn[0] + "\'" not in fn[1]]
        return output

    @staticmethod
    def pprint(tree):
        for treePart in tree:
            pprint(dict(treePart._asdict()))


class MyParser(Parser, shouldHandleLeftRecursion=True):
    #
    # Start Of File
    #

    def parse(self):
        tree = []
        while self.executeIndex < len(self.tokens):
            tree.append(self.parse_start_of_file(debug=False))
        return tree

    @_("SOF : function_declaration")
    def parse_start_of_file(self, val):
        return val

    @_("SOF : statements")
    def parse_start_of_file2(self, val):
        return val

    @_("SOF : exprs")
    def parse_start_of_file3(self, val):
        return val

    #
    # Function
    #

    @_("function_declaration : func function_name parameter_clause function_body")
    def parse_function_definition(self, name, parameters, body):
        return FunctionNode(name, parameters, body)

    @_("function_name : identifier")
    def parse_function_name(self, name):
        return name

    @_("parameter_clause : ( parameter_list )")
    def parse_parameter_clause(self, parameters):
        return parameters

    @_("parameter_clause : ( )")
    def parse_parameter_clause2(self):
        return []

    @_("function_body : { statements }")
    def parse_function_body(self, body):
        return body

    @_("function_body : { }")
    def parse_function_body2(self):
        return []

    #
    # Parameter
    #

    @_("parameter_list : parameter , parameter_list")
    def parse_parameter_list(self, parameter, parameters):
        return [parameter, *parameters]

    @_("parameter_list : parameter")
    def parse_parameter_list2(self, parameter):
        return [parameter]

    @_("parameter : hint name : type = default_value")
    def parse_parameter(self, hint, name, parameter_type, default):
        return ParameterNode(hint, name, parameter_type, default)

    @_("parameter : name : type = default_value")
    def parse_parameter1(self, name, parameter_type, default):
        return ParameterNode(hint=name, name=name, type=parameter_type, default=default)

    @_("parameter : hint name = default_value")
    def parse_parameter2(self, hint, name, default):
        return ParameterNode(hint=hint, name=name, type='Any', default=default)

    @_("parameter : hint name : type")
    def parse_parameter3(self, hint, name, parameter_type):
        return ParameterNode(hint=name, name=name, type=parameter_type, default=None)

    @_("parameter : name = default_value")
    def parse_parameter4(self, name, default):
        return ParameterNode(hint=name, name=name, type='Any', default=default)

    @_("parameter : name : type")
    def parse_parameter5(self, name, parameter_type):
        return ParameterNode(hint=name, name=name, type=parameter_type, default=None)

    @_("parameter : hint name")
    def parse_parameter6(self, hint, name):
        return ParameterNode(hint=hint, name=name, type='Any', default=None)

    @_("parameter : name")
    def parse_parameter7(self, name):
        return ParameterNode(hint=name, name=name, type='Any', default=None)

    @_("hint : identifier")
    def parse_hint(self, value):
        return value

    @_("name : identifier")
    def parse_name(self, value):
        return value

    @_("type : identifier")
    def parse_type(self, value):
        return value

    @_("default_value : literal")
    def parse_default_value(self, value):
        return value

    #
    # Assignment
    #

    @_("assignment : var identifier = expr")
    def parse_assignment1(self, name, value):
        return DynamicAssignmentNode(name, 'Any', value)

    @_("assignment : var identifier : type = expr")
    def parse_assignment2(self, name, variable_type, value):
        return DynamicAssignmentNode(name, variable_type, value)

    @_("assignment : let identifier = expr")
    def parse_assignment3(self, name, value):
        return StaticAssignmentNode(name, 'Any', value)

    @_("assignment : let identifier : type = expr")
    def parse_assignment4(self, name, variable_type, value):
        return StaticAssignmentNode(name, variable_type, value)

    #
    # Call
    #

    @_("call : identifier ( exprs )")
    def parse_call(self, name, args):
        return CallNode(name, args)

    #
    # Statements
    #

    @_("statements : statements statement")
    def parse_statements(self, statement, statements):
        return [statement, *statements]

    @_("statements : statement")
    def parse_statements2(self, statement):
        return [statement]

    """
    @_("statements : statement statements")
    def parse_statements(self, statement, statements):
        return [statement, *statements]

    @_("statements : statement")
    def parse_statements2(self, statement):
        return [statement]
    """

    #
    # Statement
    #

    @_("statement : function_declaration")
    def parse_statement_funcdef(self, val):
        return val

    @_("statement : assignment")
    def parse_statement_assign(self, val):
        return val

    @_("statement : call")
    def parse_statement_call(self, val):
        return val

    #
    # Expressions
    #

    @_("exprs : expr exprs")
    def parse_exprs(self, expr, exprs):
        return [expr, *exprs]

    @_("exprs : expr")
    def parse_exprs2(self, expr):
        return [expr]

    #
    # Expression
    #

    @_("expr : expr + term")
    def parse_sum(self, expr1, op, term2):
        return BinaryOperationNode(expr1, op, term2)

    @_("expr : term")
    def parse_sum2(self, term):
        return term

    @_("term : term * factor")
    def parse_mult(self, term1, op, factor2):
        return BinaryOperationNode(term1, op, factor2)

    @_("term : factor")
    def parse_mult2(self, factor):
        return factor

    # factor

    @_("factor : ( expr )")
    def parse_facotr_list(self, expr):
        return expr

    @_("factor : identifier")
    def parse_factor_identifier(self, val):
        return val

    @_("factor : literal")
    def parse_factor_literal(self, val):
        return val

    #
    # Endpoint
    #

    @_("identifier : _")
    def parse_identifier(self, value):
        return IdentifierNode(str(value))

    @_("literal : _")
    def parse_literal(self, value):
        value = eval(value)
        value = value if type(value) != str else '"' + value + '"'
        return LiteralNode(value)


FunctionNode = namedtuple("FunctionNode", ("name", "parameters", "body"))
ParameterNode = namedtuple("ParameterNode", ("hint", "name", "type", "default"))
DynamicAssignmentNode = namedtuple("DynamicAssignmentNode", ("name", "type", "value"))
StaticAssignmentNode = namedtuple("StaticAssignmentNode", ("name", "type", "value"))
CallNode = namedtuple("CallNode", ("name", "arguments"))
BinaryOperationNode = namedtuple("BinaryOperationNode", ("expr1", "operator", "expr2"))
IdentifierNode = namedtuple("IdentifierNode", "value")
LiteralNode = namedtuple("LiteralNode", "value")
