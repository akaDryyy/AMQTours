from itertools import combinations

def getAliases(ALIAS_PATH):
    aliases = {}
    with open(ALIAS_PATH, 'r', encoding='utf-8') as f:
        # tab-separated list of aliases, where every line has all names of one player 
        # first of each line should be the main name (current bot name)
        for line in f:
            alias_list = line.split('\t')
            main_name = alias_list[0].strip().lower()
            for alias in alias_list:
                aliases[alias.strip().lower()] = main_name
        # aliases = set()

        # for line in f:
        #     alias_list = [n.strip().lower() for n in line.split('\t')]
        #     for a, b in combinations(alias_list, 2):
        #         aliases.add((a, b))
    return aliases