import inspect

# needs this because decorator does not know class Parser below
# therefore it wouldn't know self._decorated_methods


class Generator:
    _decorated_methods = []


class Generator(Generator):
    def __init__(self, ast):
        self.ast = ast

        self.defined_dynamic_variables = []
        self.defined_static_variables = []

    def generate(self):
        code = []
        for expr in self.ast:
            func = self._get_method(expr.__class__.__name__)
            code.append(func(self, expr))
        return "\n".join(code)

    @property
    def defined_variables(self):
        return self.defined_dynamic_variables + self.defined_static_variables

    @defined_variables.setter
    def defined_variables(self, value):
        if value.isupper():
            self.defined_static_variables.append(value)
        else:
            self.defined_dynamic_variables.append(value)

    def _(parameters: str, shouldIndent=False):
        def decorator(func):
            def wrapper(self, node, indent=0):
                arguments = inspect.getargspec(func).args[1:]

                if shouldIndent:
                    kwargs = {'indent': indent}
                else:
                    kwargs = {}

                for key, value in zip(arguments, node._asdict().values()):
                    if type(value) in (list, tuple):
                        value_list = []
                        for subvalue in value:
                            value_list.append(self._tryGenerating(subvalue, indent))
                        kwargs[key] = value_list
                    else:
                        kwargs[key] = self._tryGenerating(value, indent)

                return func(self, **kwargs)

            Generator._decorated_methods.append((parameters, wrapper))
            return wrapper
        return decorator

    def _is_method_avalable(self, method_name):
        return method_name in self._get_avalable_methods()

    def _get_avalable_methods(self):
        return list(map(lambda method: method[0], self._decorated_methods))

    def _get_method(self, withName):
        avalable_decorators = list(filter(lambda method: method[0] == withName, self._decorated_methods))
        assert len(avalable_decorators) == 1, f"too many or too little avalable decorators with name {withName}, got {avalable_decorators}, {len(avalable_decorators)}"
        return avalable_decorators[0][1]

    def _tryGenerating(self, method_name, indent):
        if self._is_method_avalable(method_name.__class__.__name__):
            return self._get_method(method_name.__class__.__name__)(self, method_name, indent=indent + 1)
        else:
            return method_name

    @_("FunctionNode", shouldIndent=True)
    def generate_function_definition(self, name, parameters, body, indent=0):
        offset = " " * (4 * indent)
        parameters = ", ".join(parameters)
        body = "\n".join(body)
        return offset + f"def {name}({parameters}): \n{body}\n"

    @_("ParameterNode")
    def generate_parameter(self, hint, name, param_type, default):
        self.defined_dynamic_variables.append(name)

        return f"{name}: {param_type} = {default}" if param_type is not 'Any' else f"{name} = {default}"

    @_("StaticAssignmentNode", shouldIndent=True)
    def generate_statassign(self, name, param_type, value, indent=0):
        self.defined_static_variables.append(name.upper())

        offset = " " * (4 * indent)
        return offset + f"{name.upper()}: {param_type} = {value}" if param_type is not 'Any' else offset + f"{name.upper()} = {value}"

    @_("DynamicAssignmentNode", shouldIndent=True)
    def generate_dynassing(self, name, param_type, value, indent=0):
        self.defined_dynamic_variables.append(name)

        offset = " " * (4 * indent)
        return offset + f"{name}: {param_type} = {value}" if param_type is not 'Any' else offset + f"{name} = {value}"

    @_("CallNode", shouldIndent=True)
    def generate_call(self, name, parameters, indent=0):
        offset = " " * (4 * indent)

        for i, parameter in enumerate(parameters):
            if type(parameter) is str:
                assert parameter in self.defined_variables, "variable {parameter} is not defined"

            else:
                parameters[i] = str(parameter)

        parameters = ", ".join(parameters)

        return offset + f"{name}( {parameters} )"

    @_("IdentifierNode")
    def generate_identifier(self, value):
        return value

    @_("LiteralNode")
    def generate_literal(self, value):
        return value
