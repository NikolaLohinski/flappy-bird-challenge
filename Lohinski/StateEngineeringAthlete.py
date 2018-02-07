import sys
import pickle
import numpy as np
from os import path
from math import floor
from ple.games.flappybird import FlappyBird
from ple import PLE

DOWN = 0
UP = 1
ACTIONS = [0, 119]
PATH_TO_MODELS = path.join('.', '.models')


class Athlete:
    def __init__(
            self,
            gamma=0.75,
            alpha=0.55,
            x_reduce=10,
            y_reduce=10,
            v_reduce=1
    ):
        self.gamma = gamma
        self.alpha = alpha
        self.x_reduce = x_reduce
        self.y_reduce = y_reduce
        self.v_reduce = v_reduce
        self.max = 0
        self.Q = dict()
        self.print_data = dict()

    def state2coord(self, state):
        gap_top = state.get('next_pipe_top_y')
        bird_y = state.get('player_y')
        player_vel = state.get('player_vel')
        pipe_x = state.get('next_pipe_dist_to_player')
        return ','.join([
            str(floor(pipe_x / self.x_reduce)),
            str(floor((gap_top - bird_y) / self.y_reduce)),
            str(floor(player_vel / self.v_reduce))
        ])

    def train(self, episodes=1000):
        self.print_data = dict({
            'hits': 0,
            'games_played': 1,
            'below_15': 0,
            'pipes_below_15': 0,
            'ep': 0,
            'pipes': 0,
            'episodes': episodes
        })
        game = FlappyBird()
        env = PLE(game,
                  fps=30,
                  frame_skip=1,
                  num_steps=1,
                  force_fps=True,
                  display_screen=False)
        env.init()
        for _ in range(episodes):
            self.print_data['ep'] += 1
            env.reset_game()
            self.print_data['pipes'] = 0
            S = self.state2coord(game.getGameState())
            while not env.game_over():
                if self.Q.get(S) is None:
                    self.Q[S] = np.array([0, 0])
                A = np.argmax(self.Q[S])
                r = env.act(ACTIONS[A])
                if r == 1.0:
                    self.print_data['pipes'] += 1
                R = self.biase_reward(r)
                S_ = self.state2coord(game.getGameState())
                self.update_q(S, A, R, S_)
                S = S_
            self.print_status()

    def act(self, state):
        S = self.state2coord(state)
        if self.Q.get(S) is None:
            return DOWN
        return np.argmax(self.Q[S])


    def biase_reward(self, r):
        return (10 if r == 0. else 100) if r != -5. else -1000
        # return (1 if r == 0. else 2) if r != -5. else -1
        # return floor(r)

    def update_q(self, S, A, R, S_):
        if self.Q.get(S_) is not None:
            delta = R + self.gamma * np.max(self.Q[S_]) - self.Q[S][A]
            self.Q[S][A] += self.alpha * delta

    def print_status(self):
        nb_pipes = self.print_data['pipes']
        epoch = self.print_data['ep']
        horizon = self.print_data['episodes']
        sum_nb_pipes = self.print_data['hits']
        nb_games = self.print_data['games_played']
        nb_games_under_15 = self.print_data['below_15']
        sum_nb_pipes_under_15 = self.print_data['pipes_below_15']
        if nb_pipes > self.max:
            print('\nNew max: {} pipes, on game {}'.format(nb_pipes, epoch + 1))
            print('In previous sequence:')
            print(' - Average: {} pipes'.format(
                np.round(sum_nb_pipes / nb_games, decimals=1)
            ))
            print(' - games < 15: {}/{} ({}%)'.format(
                nb_games_under_15,
                nb_games,
                np.round(100 * nb_games_under_15 / nb_games, decimals=1))
            )
            print(' - Average of games < 15: {} pipes'.format(
                np.round(sum_nb_pipes_under_15 / nb_games, decimals=1)
            ))
            print(' - Number of Q states: {}'.format(len(self.Q)))
            self.max = nb_pipes
            self.print_data['hits'] = nb_pipes
            self.print_data['pipes_below_15'] = 0
            self.print_data['games_played'] = 1
            self.print_data['below_15'] = 1 if nb_pipes < 15 else 0
        else:
            if nb_pipes < 15:
                self.print_data['pipes_below_15'] += nb_pipes
                self.print_data['below_15'] += 1
            self.print_data['hits'] += nb_pipes
            self.print_data['games_played'] += 1
        if self.print_data['ep'] % floor(
                horizon / 10 if horizon < 10000 else horizon / 100
        ) == 0:
            print('Games: {}/{} ({}%)'.format(
                epoch,
                horizon,
                (100 * epoch / horizon))
            )

    def save_model(self, name=None):
        if name is None:
            name = 'StateEngineeringModel.pkl'
        file_path = path.join(PATH_TO_MODELS, name)
        if path.isfile(file_path):
            r = input('File {} already exists. Overwrite ? (y,[n]) '.format(name))
            if r != 'y':
                name = 'bis_{}'.format(name)
                self.save_model(name=name)
                return
        to_save = dict({
            'Q': self.Q,
            'gamma': self.gamma,
            'alpha': self.alpha,
            'x_reduce': self.x_reduce,
            'y_reduce': self.y_reduce,
            'v_reduce': self.v_reduce
        })
        with open(file_path, 'wb+') as f:
            pickle.dump(to_save, f, pickle.HIGHEST_PROTOCOL)

    def load_model(self, file_path):
        with open(file_path, 'rb') as f:
            saved = dict(pickle.load(f))
            self.Q = saved.get('Q')
            self.gamma = saved.get('gamma')
            self.alpha = saved.get('alpha')
            self.x_reduce = saved.get('x_reduce')
            self.y_reduce = saved.get('y_reduce')
            self.v_reduce = saved.get('v_reduce')

    def play(self, fast=True):
        game = FlappyBird()
        env = PLE(game,
                  fps=30,
                  frame_skip=1,
                  num_steps=1,
                  force_fps=fast,
                  display_screen=not fast)
        env.init()
        pipes = []
        i = 0
        while i < 100:
            env.reset_game()
            pipes.append(0)
            while not env.game_over():
                A = self.act(game.getGameState())
                r = env.act(ACTIONS[A])
                if r == 1.:
                    pipes[-1] += 1
            if not fast:
                print('\n- Score: {} pipes'.format(pipes[-1]))
                print('- Played {} games'.format(len(pipes)))
                print('- Average score: {} pipes'.format(np.round(np.mean(pipes), decimals=1)))
            else:
                i += 1

        print('\n- Max score: {} pipes'.format(np.max(pipes)))
        print('- Games < 15 pipes: {}'.format(len(tuple(filter(lambda x: x < 15, pipes)))))
        print('- Played {} games'.format(100))
        print('- Average score: {} pipes'.format(np.round(np.mean(pipes), decimals=1)))


if __name__ == '__main__':
    athlete = Athlete()
    epochs = 10000
    no_train = False
    test_only = False
    save_name = None
    if len(sys.argv) > 1:
        try:
            args = sys.argv[1:]
            commands = filter(lambda x: '--' in x, args)
            if any([x not in [
                '--load', '--epochs', '--play', '--save', '--test'
            ] for x in commands]):
                raise IndexError
            if '--load' in args:
                index = args.index('--load')
                path_to_file = args[index + 1]
                athlete.load_model(file_path=path_to_file)
                if '--play' in args:
                    no_train = True
                if '--test' in args:
                    no_train = True
                    test_only = True
            if '--save' in args:
                index = args.index('--save')
                save_name = args[index + 1]
            if '--epochs' in args:
                index = args.index('--epochs')
                epochs = int(args[index + 1])
            if '--load' not in args and ('--play' in args or '--test' in args):
                print('Can not play/test without loading a model.')
                raise IndexError
        except IndexError:
            print('Error. Please give the correct inputs as described below:')
            print('--load <path_to_model.pkl>,\n'
                  '--epochs <nb_of_epochs>,\n'
                  '--save <name_of_save_file.pkl>,\n'
                  '--test,\n'
                  '--play'.format(__file__))
            sys.exit(1)
    if not no_train:
        try:
            athlete.train(episodes=epochs)
        except KeyboardInterrupt:
            print('User stopped training')
        print('Nb Q states : {}'.format(len(athlete.Q)))
        print('Max score : {}'.format(athlete.max))
        athlete.save_model(name=save_name)
    athlete.play(fast=test_only)
