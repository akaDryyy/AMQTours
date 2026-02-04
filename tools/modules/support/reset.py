def reset_whitelist(WHITELIST_PATH):
    reset_whitelist = """[
    ["playerA", "playerB"],
    ["playerC", "playerD"]
]"""

    with open(WHITELIST_PATH, "w") as f:
        f.write(reset_whitelist)

def reset_ranks(RANKS_PATH):
    reset_ranks = """11:
10:
9:"""

    with open(RANKS_PATH, "w") as f:
        f.write(reset_ranks)