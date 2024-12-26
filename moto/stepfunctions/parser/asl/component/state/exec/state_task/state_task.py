from __future__ import annotations

import abc
from typing import List, Optional

from moto.stepfunctions.parser.api import HistoryEventType, TaskTimedOutEventDetails
from moto.stepfunctions.parser.asl.component.common.error_name.failure_event import (
    FailureEvent,
)
from moto.stepfunctions.parser.asl.component.common.error_name.states_error_name import (
    StatesErrorName,
)
from moto.stepfunctions.parser.asl.component.common.error_name.states_error_name_type import (
    StatesErrorNameType,
)
from moto.stepfunctions.parser.asl.component.common.parargs import Parargs
from moto.stepfunctions.parser.asl.component.state.exec.execute_state import (
    ExecutionState,
)
from moto.stepfunctions.parser.asl.component.state.exec.state_task.credentials import (
    ComputedCredentials,
    Credentials,
)
from moto.stepfunctions.parser.asl.component.state.exec.state_task.service.resource import (
    Resource,
)
from moto.stepfunctions.parser.asl.component.state.state_props import StateProps
from moto.stepfunctions.parser.asl.eval.environment import Environment
from moto.stepfunctions.parser.asl.eval.event.event_detail import EventDetails


class StateTask(ExecutionState, abc.ABC):
    resource: Resource
    parargs: Optional[Parargs]
    credentials: Optional[Credentials]

    def __init__(self):
        super(StateTask, self).__init__(
            state_entered_event_type=HistoryEventType.TaskStateEntered,
            state_exited_event_type=HistoryEventType.TaskStateExited,
        )

    def from_state_props(self, state_props: StateProps) -> None:
        super(StateTask, self).from_state_props(state_props)
        self.resource = state_props.get(Resource)
        self.parargs = state_props.get(Parargs)
        self.credentials = state_props.get(Credentials)

    def _get_supported_parameters(self) -> Optional[Set[str]]:  # noqa
        return None

    def _eval_parameters(self, env: Environment) -> dict:
        # Eval raw parameters.
        parameters = dict()
        if self.parargs is not None:
            self.parargs.eval(env=env)
            parameters = env.stack.pop()

        # Handle supported parameters.
        supported_parameters = self._get_supported_parameters()
        if supported_parameters:
            unsupported_parameters: List[str] = [
                parameter
                for parameter in parameters.keys()
                if parameter not in supported_parameters
            ]
            for unsupported_parameter in unsupported_parameters:
                parameters.pop(unsupported_parameter, None)

        return parameters

    def _eval_credentials(self, env: Environment) -> ComputedCredentials:
        if not self.credentials:
            task_credentials = dict()
        else:
            self.credentials.eval(env=env)
            task_credentials = env.stack.pop()
        return task_credentials

    def _get_timed_out_failure_event(self, env: Environment) -> FailureEvent:
        return FailureEvent(
            env=env,
            error_name=StatesErrorName(typ=StatesErrorNameType.StatesTimeout),
            event_type=HistoryEventType.TaskTimedOut,
            event_details=EventDetails(
                taskTimedOutEventDetails=TaskTimedOutEventDetails(
                    error=StatesErrorNameType.StatesTimeout.to_name(),
                )
            ),
        )

    def _from_error(self, env: Environment, ex: Exception) -> FailureEvent:
        if isinstance(ex, TimeoutError):
            return self._get_timed_out_failure_event(env)
        return super()._from_error(env=env, ex=ex)
