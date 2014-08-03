#! /usr/bin/python

import sgflib
import argparse
import os
import subprocess
import sys

class SGF_Game(object):
    """SGF_Game Object"""
    def __init__(self, sgf_path):
        super(SGF_Game, self).__init__()
        self.game_tree = self._load_sgf(sgf_path)
        self.sgf_out = None

    def _load_sgf(self, sgf_path):
        """ Loads an sgf file and returns the parsed game tree"""
        sgf_file = open(sgf_path, "r+")
        parser = sgflib.SGFParser(sgf_file.read())
        sgf_file.close()
        raw_tree = parser.parseOneGame()
        return raw_tree.mainline()

    def _get_notations(self, node):
        """Gets list of notations from a game node"""
        node_notations = node.get("LB", None)
        if node_notations:
            note_list = node_notations.data
        else:
            note_list = []
        return note_list

    def _generate_comments(self, best_play_value, node_play_value):
        """Generates comments for each reviewed game node"""
        generic_comments = '''

        Gnu Go has marked its favorite moves as
        capitol letters, with 'A' being its favorite

        Gnu Go will mark groups that are unsettled with '!'
        Gnu Go will mark groups that might be beyond help with 'X'
        '''

        if best_play_value and node_play_value:
            agreement = (float(node_play_value) / float(best_play_value)*100)
            comments = 'Gnu go agrees with this move %0.2f%%' % (agreement)
        else:
            comments = 'Gnu go thinks this move is very creative!'

        return comments + generic_comments

    def review(self, num_alt_moves):
        """Uses game tree to generate automatic review"""
        for node in self.game_tree:
            #Get relevant game node info
            note_list = self._get_notations(node)
            clean_notes = []
            gnu_value_notes = {}
            node_comments = node.get("C", None)
            node_play_value = None
            best_play_value = None
            node_player_move = "None"

            if 'W' in node.data:
                node_player_move = node.get('W')[0]
            if 'B' in node.data:
                node_player_move = node.get('B')[0]

            if note_list:
                for note in note_list:
                    #Separate coordinate from the note text
                    note_location, note_text = note[0:2], note[3:]
                    #If the note is a numeric value its GNU GO
                    #telling us what it thinks of that location
                    if note_text.isdigit():
                        #We want to know if gnugo had an opinion of the players move
                        if note_location == node_player_move:
                            node_play_value = float(note_text)
                            #clean_notes.append('%s:%s' % (note_location, note_text))
                        #Save all numeric notes from gnugo in dict for sorting
                        gnu_value_notes[note_location] = note_text
                    else:
                        #If the note is not numeric just pass it through to the final SGF
                        if not note_text == "<1":
                            clean_notes.append('%s:%s' % (note_location, note_text))

                #For all the numeric notes from gnugo
                #Get the top num_alt_moves sorted highest to lowest.
                #For the top num_alt_moves append the highest to the list.
                for index, item in enumerate(sorted(gnu_value_notes.iteritems(),
                                                    key=lambda (k,v): (int(v),k),
                                                    reverse=True)[0:4]):
                    #Capture numeric val of top gnu go play
                    if index == 0:
                        best_play_value = float(item[1])
                    #chr(0+65) = 'A' #chr(1+65) = 'B' etc...
                    clean_notes.append('%s:%s' % (item[0], chr(index + 65)))

                node['LB'].data = clean_notes
                node['C'].data = self._generate_comments(best_play_value, node_play_value)
                if 'CR' in node.data:
                    node['CR'].data = ''

        return self.game_tree.__str__()

class CliTools(object):
    """CliTools Object"""
    def __init__(self, root):
        super(CliTools, self).__init__()
        self.root = root

    def run_command_with_code(self, cmd, redirect_output=True,
                                  check_exit_code=True):
        """Runs a command in an out-of-process shell.
        Returns the output of that command. Working directory is self.root.
        """
        if redirect_output:
            stdout = subprocess.PIPE
        else:
            stdout = None

        proc = subprocess.Popen(cmd, cwd=self.root, stdout=stdout)
        output = proc.communicate()[0]
        if check_exit_code and proc.returncode != 0:
            self.die('Command "%s" failed.\n%s', ' '.join(cmd), output)
        return (output, proc.returncode)

    def die(self, message, *args):
        print(message % args)
        sys.exit(1)

    def run_command(self, cmd, redirect_output=True, check_exit_code=True):
        return self.run_command_with_code(cmd, redirect_output,
                                          check_exit_code)[0]

    def parse_args(self, argv):
        """Parses command-line arguments."""
        parser =  argparse.ArgumentParser()
        parser.add_argument('-o', '--output',
                            help="output file name",
                            required=True)
        parser.add_argument('-i', '--input',
                            help="input file name",
                            required=True)
        parser.add_argument('-l', '--level', help="gnugo level, default:15",
                            default='15')
        parser.add_argument('-s', '--suggest',
                            help="number of moves to suggest, default:4",
                            type=int,
                            default=4)
        return parser.parse_args()

if __name__ == "__main__":

    root = os.path.dirname(os.path.realpath(__file__))

    clitools = CliTools(root)
    options = clitools.parse_args(sys.argv)

    raw_game = options.input
    gnugo_level = options.level

    gnugo_cmd = ["gnugo", "--level", gnugo_level, "--output-flags", "dv",
                 "--replay", "both", "-l", raw_game, "-o", "gnurev.sgf"]

    clitools.run_command(gnugo_cmd, redirect_output=False, check_exit_code=False)

    sgf_game = SGF_Game("gnurev.sgf")
    print "Reviewing GNUGO Notation"
    reviewed_game = sgf_game.review(options.suggest)
    new_sgf_file = open(options.output, "w")
    print "Writing Notated file"
    new_sgf_file.write(reviewed_game)
    new_sgf_file.close()
