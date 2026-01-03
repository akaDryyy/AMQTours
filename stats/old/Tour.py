import os, json, re
import sys

DIRECTORY = os.path.dirname(__file__) + "/jsons/"
REGEX = "\D*(\d{1,2})\s*(\(.*?\))?\.json$"

class Player:
    def __init__(self, name):
        self.name = name
        self.total_diff = self.rigs = self.rigs_hit = 0
        self.rounds_played = 1
        self.dog = [0]*8
        self.correct_songs = [0]*3
        self.total_songs = [0]*3
        self.rating = 0
        
    def update_total(self, total_songs):
        self.total_songs = [a + b for a, b in zip(self.total_songs, total_songs)]
        
    def update_correct(self, correct_songs):
        self.correct_songs = [a + b for a, b in zip(self.correct_songs, correct_songs)]
        
    def update_dog(self, dog):
        self.dog = [a + b for a, b in zip(self.dog, dog)]
        
    def update_all(self, new):
        self.total_diff += new.total_diff
        self.rigs += new.rigs
        self.rigs_hit += new.rigs_hit
        self.rounds_played += new.rounds_played
        self.update_total(new.total_songs)
        self.update_correct(new.correct_songs)
        self.update_dog(new.dog)
        self.rating += new.rating
        
        
class Game:
    def __init__(self, file_name):
        self.players = []
        self.total_songs = [0]*3
        self.songs_info = dict()
        self.calculate_game(file_name)
        
    def get_all_names(self):
        return [player.name for player in self.players]
        
    def get_player_by_name(self, name):
        for player in self.players:
            if player.name == name:
                return player
        return None
        
    def calculate_game(self, file_name):
        # If default name, just use all songs
        if file_name.startswith('amq_song_expoert'):
            songs_played = None
        else:
            reg_match = re.search(REGEX, file_name)
            if reg_match is None:
                songs_played = None
            else:
                songs_played = int(reg_match.group(1))
        
        with open(DIRECTORY + file_name,encoding="utf8") as f:
            try:
                data = json.load(f)
            except:
                print(f"Failed to load {f} are you sure that this is the right file?")
                sys.exit(1)

        try:
            for song in data['songs'][:songs_played]:
                # Probably downloaded after the user disconnected or refreshed the page
                if 'videoUrl' not in song:
                    print(f"The following file is incomplete: {file_name}. Maybe a disconnect occurred?")
                    sys.exit(1)

                song_file = song['videoUrl'].split('/')[-1]
                if song_file not in self.songs_info:
                    self.songs_info[song_file] = song['songInfo']
                    self.songs_info[song_file]['count'] = 0
                self.songs_info[song_file]['count'] += 1

                song_type = song["songInfo"]["type"]
                self.total_songs[song_type-1]+=1
                correct_count = int(song['correctCount'])
                
                for player_name in song['listStates']:
                    player = self.get_player_by_name(player_name["name"])
                    if player is None:
                        player = Player(player_name["name"])
                        self.players.append(player)
                    player.rigs+=1
                    if player.name in song['correctGuessPlayers']:
                        player.rigs_hit+=1
                if not correct_count:
                    continue

                  
                for player_name in song['correctGuessPlayers']:
                    player = self.get_player_by_name(player_name)
                    if player is None:
                        player = Player(player_name)
                        self.players.append(player)
                    player.correct_songs[song_type-1]+=1
                    player.dog[correct_count-1]+=1
                    if song['songInfo']['animeDifficulty'] != "Unrated":
                        player.total_diff += song['songInfo']['animeDifficulty']
        except Exception as e:
            print("Uncaught error:", file_name, e)

        while len(self.players) < 8:
            print(self.get_all_names())
            player_name = input("[{}] Input missing player name(case sensitive):".format(file_name))
            if player_name in self.get_all_names():
                print("{} is not missing".format(player_name))
                continue
            self.players.append(Player(player_name))
            
        for player in self.players:
            player.update_total(self.total_songs)

class Tour:
    def __init__(self, debug=False):
        self.players = []
        self.__song_infos = dict()
        self.calculate_all_games()
        self.debug = debug

        self.top_songs = [[song_file, song_info['count']] for song_file, song_info in self.__song_infos.items()]
        self.top_songs = [[f"{self.__song_infos[song_file]['songName']} ({self.__song_infos[song_file]['animeNames']['romaji']})", play_count] for [song_file, play_count] in sorted(self.top_songs, key=lambda pair: pair[1], reverse=True)[:10] if play_count > 1]

        if self.debug:
            player_info = [f"{player.name}-{player.rounds_played}" for player in self.players]
            print(f"Players: {player_info} ({len(self.players)})\n")

    def get_player_by_name(self, name):
        for player in self.players:
            if player.name == name:
                return player
        return None

    def calculate_all_games(self):
        for file_name in os.listdir(DIRECTORY):
            if file_name.endswith(".json"):
                game = Game(file_name)
                for song_file, song_info in game.songs_info.items():
                    if song_file not in self.__song_infos:
                        self.__song_infos[song_file] = song_info
                    else:
                        self.__song_infos[song_file]['count'] += song_info['count']
                for player in game.players:
                    if self.get_player_by_name(player.name) is None:
                        self.players.append(player)
                    else:
                        self.get_player_by_name(player.name).update_all(player)
