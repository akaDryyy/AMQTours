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
    return aliases