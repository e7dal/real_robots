# -*- coding: utf-8 -*-

import gym
from .envs import Goal  # noqa F401
from .policy import BasePolicy
import numpy as np

from tqdm.auto import tqdm

"""Local evaluation helper functions."""


def build_score_object(scores):
    total_score = 0
    challenges = ['2D', '2.5D', '3D']

    score_object = {}
    for key in challenges:
        if key in scores.keys():
            results = scores[key]
            challenge_score = np.mean(results)
        else:
            results = []
            challenge_score = 0
        total_score += challenge_score
        score_object["score_{}".format(key)] = challenge_score
    total_score /= len(challenges)

    score_object["score_total"] = total_score
    return score_object


def evaluate(Controller,
             intrinsic_timesteps=1e7,
             extrinsic_timesteps=2e3,
             extrinsic_trials=350,
             visualize=True,
             goals_dataset_path="./goals.npy.npz"):
    """
    A wrapper function to locally simulate the evaluation process
    as is done for all the submitted controllers.

    Parameters
    ----------
    Controller
        An example controller which should expose a `step` function, for
        the evaluator to compute the `action` given observation, reward
        and done info

    intrinsic_timesteps: int, bool
        Maximum number of timesteps in the Intrinsic phase.
        If set to False, then
    extrinsic_timesteps: int
        Maximum number of timesteps in the Extrinsic phase
    extrinsic_trials: int
        Total number of trials in the extrinsic phase
    visualize: bool
        Boolean flag which enables or disables the visualizer when
        running the evaluation
    goals_dataset_path: str
        Path to a goals dataset
    """
    env = gym.make('REALRobot-v0')
    env.set_goals_dataset_path(goals_dataset_path)

    if visualize:
        env.render('human')

    if not issubclass(Controller, BasePolicy):
        raise Exception(
                "Supplied Controller is not a Sub-Class of "
                "real_robots.policy.BasePolicy . Please ensure that "
                "the supplied controller class is derived from "
                "real_robots.policy.BasePolicy , as described in the "
                "example here at: "
                "https://github.com/AIcrowd/real_robots#usage"
            )

    controller = Controller(env.action_space)

    env.intrinsic_timesteps = intrinsic_timesteps  # default = 1e7
    env.extrinsic_timesteps = extrinsic_timesteps  # default = 2e3

    # Setup Evaluation State
    ##########################################################
    """
    State Transitions:
    overall_state:
        PENDING -> INTRINSIC_PHASE_IN_PROGRESS
        INTRINSIC_PHASE_IN_PROGRESS -> INTRINSIC_PHASE_COMPLETE
        INTRINSIC_PHASE_COMPLETE -> EXTRINSIC_PHASE_IN_PROGRESS
        EXTRINSIC_PHASE_IN_PROGRESS -> EXTRINSIC_PHASE_COMPLETE
        ERROR
        EVALUATION_COMPLETE
    intrinsic_phase_state:
        PENDING
        INTRINSIC_PHASE_IN_PROGRESS
        INTRINSIC_PHASE_COMPLETE
        INTRINSIC_PHASE_SKIPPED
        INTRINSIC_PHASE_ERROR
    extrinsic_phase_state:
        PENDING
        EXTRINSIC_PHASE_IN_PROGRESS
        EXTRINSIC_PHASE_COMPLETE
        EXTRINSIC_PHASE_ERROR
    """
    evaluation_state = {  # noqa
        "state": "PENDING",
        "max_intrinsic_timesteps": intrinsic_timesteps,
        "max_extrinsic_timesteps": extrinsic_timesteps,
        "current_intrinsic_timestep": 0,
        "max_extrinsic_trials": extrinsic_trials,
        "num_extrinsic_trials_complete": 0,
        "progress_in_current_extrinsic_trial": 0,
        "score": {
            "score": 0,
            "score_2D": 0,
            "score_2.5D": 0,
            "score_3D": 0,
            "score_total": 0
        }
    }

    # Helper functions
    ##########################################################
    scores = {}

    def add_scores(challenge, score):
        if challenge in scores.keys():
            scores[challenge] += [score]
        else:
            scores[challenge] = [score]
    ##########################################################
    if not intrinsic_timesteps:
        # Set intrinsic_timesteps = 0 if its set as False
        intrinsic_timesteps = 0

    if intrinsic_timesteps > 0:
        observation = env.reset()
        reward = 0
        done = False
        intrinsic_phase_progress_bar = tqdm(
                            total=intrinsic_timesteps,
                            desc="Intrinsic Phase",
                            unit="steps ",
                            leave=True
                            )
        intrinsic_phase_progress_bar.write(
                    "######################################################"
                )
        intrinsic_phase_progress_bar.write("# Intrinsic Phase Initiated")
        intrinsic_phase_progress_bar.write(
                    "######################################################"
                )

        # intrinsic phase
        steps = 0
        # Notify the controller that the intrinsic phase started
        controller.start_intrinsic_phase()
        while not done:
            # Call your controller to chose action
            action = controller.step(observation, reward, done)
            # do action
            observation, reward, done, _ = env.step(action)
            steps += 1
            intrinsic_phase_progress_bar.update(1)
        intrinsic_phase_progress_bar.write(
                    "######################################################"
                )
        intrinsic_phase_progress_bar.write("# Intrinsic Phase Complete")
        intrinsic_phase_progress_bar.write(
                    "######################################################"
                )
        # Notify the controller that the intrinsic phase ended
        controller.end_intrinsic_phase()
    else:
        print("[WARNING] Skipping Intrinsic Phase as intrinsic_timesteps = 0 or False")  # noqa

    # extrinsic phase
    # tqdm.write("Starting extrinsic phase")

    extrinsic_phase_progress_bar = tqdm(
                                        total=extrinsic_trials,
                                        desc="Extrinsic Phase",
                                        unit="trials ",
                                        leave=True
                                        )
    extrinsic_phase_progress_bar.write(
                    "######################################################"
                )
    extrinsic_phase_progress_bar.write("# Extrinsic Phase Initiated")
    extrinsic_phase_progress_bar.write(
                    "######################################################"
                )

    # Notify the controller that the extrinsic phase started
    controller.start_extrinsic_phase()
    for k in range(extrinsic_trials):
        observation = env.reset()
        reward = 0
        done = False
        env.set_goal()

        # Notify the controller that an extrinsic trial started
        controller.start_extrinsic_trial()

        extrinsic_trial_progress_bar = \
            tqdm(
                total=extrinsic_timesteps,
                desc="Extrinsic Trial # {}".format(k),
                unit="steps ",
                leave=False
                )

        while not done:
            action = controller.step(observation, reward, done)
            observation, reward, done, _ = env.step(action)
            extrinsic_trial_progress_bar.update(1)

        # Notify the controller that an extrinsic trial ended
        controller.end_extrinsic_trial()

        extrinsic_trial_progress_bar.close()

        extrinsic_phase_progress_bar.update(1)
        add_scores(*env.evaluateGoal())
        extrinsic_phase_progress_bar.set_postfix(
                        build_score_object(
                                scores
                            )
                    )

    extrinsic_phase_progress_bar.write(
                    "######################################################"
                )
    extrinsic_phase_progress_bar.write("# Extrinsic Phase Complete")
    extrinsic_phase_progress_bar.write(
                    "######################################################"
                )
    extrinsic_phase_progress_bar.write(str(build_score_object(scores)))

    # Notify the controller that the extrinsic phase ended
    controller.end_extrinsic_trial()

    return build_score_object(scores)
