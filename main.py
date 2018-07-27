from tokenizer import *
from tokenParser import *
from generator import *
# from generator import *

tokens = []
tree = []
print()

tokens = Tokenizer(open('functions.swft').read()).tokenize()
pprint(tokens)
print()

parser = MyParser(tokens)
tree = parser.parse()
print(tree)
print()

generator = Generator(tree)
generated = generator.generate()
print(generated)
