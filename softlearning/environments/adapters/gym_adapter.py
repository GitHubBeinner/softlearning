"""Implements a GymAdapter that converts Gym envs into SoftlearningEnv."""

from collections import defaultdict, OrderedDict
import copy

import gym
from gym import spaces, wrappers
from gym.envs.mujoco.mujoco_env import MujocoEnv

from .softlearning_env import SoftlearningEnv
from softlearning.environments.gym import register_environments
from softlearning.environments.gym.wrappers import (
    NormalizeActionWrapper, PixelObservationWrapper)


def parse_domain_task(gym_id):
    domain_task_parts = gym_id.split('-')
    domain = '-'.join(domain_task_parts[:1])
    task = '-'.join(domain_task_parts[1:])

    return domain, task


CUSTOM_GYM_ENVIRONMENT_IDS = register_environments()
CUSTOM_GYM_ENVIRONMENTS = defaultdict(list)

for gym_id in CUSTOM_GYM_ENVIRONMENT_IDS:
    domain, task = parse_domain_task(gym_id)
    CUSTOM_GYM_ENVIRONMENTS[domain].append(task)

CUSTOM_GYM_ENVIRONMENTS = dict(CUSTOM_GYM_ENVIRONMENTS)

GYM_ENVIRONMENT_IDS = tuple(gym.envs.registry.env_specs.keys())
GYM_ENVIRONMENTS = defaultdict(list)


for gym_id in GYM_ENVIRONMENT_IDS:
    domain, task = parse_domain_task(gym_id)
    GYM_ENVIRONMENTS[domain].append(task)

GYM_ENVIRONMENTS = dict(GYM_ENVIRONMENTS)


DEFAULT_OBSERVATION_KEY = 'observations'


class GymAdapter(SoftlearningEnv):
    """Adapter that implements the SoftlearningEnv for Gym envs."""

    def __init__(self,
                 domain,
                 task,
                 *args,
                 env=None,
                 normalize=True,
                 observation_keys=(),
                 goal_keys=(),
                 unwrap_time_limit=True,
                 pixel_wrapper_kwargs=None,
                 **kwargs):
        assert not args, (
            "Gym environments don't support args. Use kwargs instead.")

        self.normalize = normalize
        self.unwrap_time_limit = unwrap_time_limit

        super(GymAdapter, self).__init__(
            domain, task, *args, goal_keys=goal_keys, **kwargs)

        if env is None:
            assert (domain is not None and task is not None), (domain, task)
            env_id = f"{domain}-{task}"
            env = gym.envs.make(env_id, **kwargs)
            self._env_kwargs = kwargs
        else:
            assert not kwargs
            assert domain is None and task is None, (domain, task)

        if isinstance(env, wrappers.TimeLimit) and unwrap_time_limit:
            # Remove the TimeLimit wrapper that sets 'done = True' when
            # the time limit specified for each environment has been passed and
            # therefore the environment is not Markovian (terminal condition
            # depends on time rather than state).
            env = env.env

        if normalize:
            env = NormalizeActionWrapper(env)

        if pixel_wrapper_kwargs is not None:
            env = PixelObservationWrapper(env, **pixel_wrapper_kwargs)

        self._env = env

        if isinstance(self._env.observation_space, spaces.Dict):
            dict_observation_space = self._env.observation_space
            self.observation_keys = (
                observation_keys or (*self.observation_space.spaces.keys(), ))
        elif isinstance(self._env.observation_space, spaces.Box):
            dict_observation_space = spaces.Dict(OrderedDict((
                (DEFAULT_OBSERVATION_KEY, self._env.observation_space),
            )))
            self.observation_keys = (DEFAULT_OBSERVATION_KEY, )

        self._observation_space = type(dict_observation_space)([
            (name, copy.deepcopy(space))
            for name, space in dict_observation_space.spaces.items()
            if name in self.observation_keys
        ])

        if len(self._env.action_space.shape) > 1:
            raise NotImplementedError(
                "Shape of the action space ({}) is not flat, make sure to"
                " check the implemenation.".format(self._env.action_space))

        self._action_space = self._env.action_space

    def step(self, action, *args, **kwargs):
        observation, reward, terminal, info = self._env.step(
            action, *args, **kwargs)

        if not isinstance(self._env.observation_space, spaces.Dict):
            observation = {DEFAULT_OBSERVATION_KEY: observation}

        observation = self._filter_observation(observation)
        return observation, reward, terminal, info

    def reset(self, *args, **kwargs):
        observation = self._env.reset()

        if not isinstance(self._env.observation_space, spaces.Dict):
            observation = {DEFAULT_OBSERVATION_KEY: observation}

        observation = self._filter_observation(observation)
        return observation

    def render(self, *args, width=100, height=100, **kwargs):
        if isinstance(self._env.unwrapped, MujocoEnv):
            self._env.render(*args, width=width, height=height, **kwargs)

        return self._env.render(*args, **kwargs)

    def seed(self, *args, **kwargs):
        return self._env.seed(*args, **kwargs)

    @property
    def unwrapped(self):
        return self._env.unwrapped
