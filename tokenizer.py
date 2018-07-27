from dataclasses import dataclass
import re


@dataclass
class TokenType:
    space: str = r'\s'
    literal: str = r'|'.join([key for key in
                              [r'\btrue\b', r'\bfalse\b', '([0-9]*\.[0-9]+|[0-9]+)', '(\"|\')[a-zA-Z0-9]*(\"|\')']])
    identifier: str = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
    operator: str = r'\=\=|\+|\-|\*|\\'
    char: str = r'.'

    def __iter__(self):
        for key, value in self.__dict__.items():
            yield key, value


@dataclass
class Token:
    type: str
    value: str


class Tokenizer:
    def __init__(self, code):
        self.TOKEN_TYPES = TokenType()
        self.code = code

    def tokenize(self):
        tokens = []

        while len(self.code) != 0:
            tokens.append(self.tokenize_one_token())
            self.code = self.code.strip()
        return tokens

    def tokenize_one_token(self):
        for (tokenType, reg) in self.TOKEN_TYPES:
            reg = "\A({reg})".format(reg=reg)
            match = re.search(reg, self.code)
            if match is not None:
                value = match.group(1)
                self.code = self.code[len(value):]
                return Token(tokenType, value)

        raise RuntimeError("Couldn't match token on {}".format(self.code))


with open('program.swft', 'r') as file:
    t = Tokenizer(file.read())
    t.tokenize()
