# -*- coding: utf-8 -*-

"""
A library used for finite-state machine.

Introductions to FSM: http://en.wikipedia.org/wiki/Finite-state_machine

Examples:

    State/Event table:
        +----+----+----+
        |    | S1 | S2 |
        +----+----+----+
        | C1 |    | S1 |
        +----+----+----+
        | C2 | S2 |    |
        +----+----+----+
        | C3 | S1 | S2 |
        +----+----+----+

    >>> class C1(Command):
    >>>     def execute(self, params):
    >>>         print "Execute C1"
    >>>
    >>> class C2(Command):
    >>>     def execute(self, params):
    >>>         print "Execute C2"
    >>>
    >>> class C3(Command):
    >>>     def execute(self, params):
    >>>         print "Execute C3"
    >>>
    >>> class S1(State):
    >>>     weight = {'c2': 1, 'c3': 1}
    >>>     def before_c2(self):
    >>>         print "State S1"
    >>>     def before_c3(self):
    >>>         print "State S1"
    >>>     def after_c2(self):
    >>>         self.switch_state_to('s2')
    >>>     def after_c3(self):
    >>>         print 'remains s1'
    >>>
    >>> class S2(State):
    >>>     weight = {'c1': 1, 'c3': 1}
    >>>     def before_c1(self):
    >>>         print "State S2"
    >>>     def before_c3(self):
    >>>         print "State S2"
    >>>     def after_c1(self):
    >>>         self.switch_state_to('s1')
    >>>     def after_c3(self):
    >>>         print "remains S2"
    >>>
    >>> sm = StateMachine(duration=10)
    >>> sm.add_state(S1, C2, C3, is_start=True)
    >>> sm.add_state(S2, C1, C3)
    >>> sm.run()
    >>>
"""

import time
import random
import threading


__VERSION__ = "0.1"


class Command(object):
    """Base Command class.
    
    User-defined commands must implement method 'execute'."""

    def __init__(self, **kwargv):
        self.__dict__ = kwargv

    def execute(self, params):
        """Command subclasses object must implement this method.
        Put all the functional codes here.
        
        :params - A dict-like parameter which holds all the value
                  returned from the previous command.
        :return - A dict-like parameter which will send to the next command."""
        raise NotImplementedError


class State(object):
    """Base State class for DFA.

    Each State object holds several Command objects. When state switches,
    State object will choose a command of Command objects pool evaluated
    by their weights, and then execute the command.

    Attributes
    :weight - float value of each command for this state, probability of
              commands execution depends on it.

    Methods
    :before_<command> - called before `command` is executed.
    :after_<command> - called after `command` is executed."""

    weight = {}

    def __init__(self, dfa, **kwargv):
        self.dfa = dfa
        self.commands = {}
        self._cmd_params = kwargv
        self._weight_sum = 0

    def _set_weight(self):
        self._weight_sum = 0
        for wname in self.weight:
            if wname not in self.commands:
                raise ValueError
            self._weight_sum += self.weight[wname]
            self.commands[wname].weight = self.weight[wname]

    def _import_commands(self, *argv):
        for a in argv:
            if not issubclass(a, Command):
                raise KeyError
            cname = a.__name__.lower()
            self.commands[cname] = a(**self._cmd_params)
        self._set_weight()

    def switch_state_to(self, name):
        """Switch current state of DFA to the specified one
        
        :name - the state name(lower charactors)"""

        if name not in self.dfa.states:
            raise self.DoesNotFound
        self.dfa.state = self.dfa.states[name]

    def command(self, name):
        """Return the command instance by name"""

        return self.commands[name]

    def choose(self):
        """Choose a command name randomly from commands pool."""

        a = random.random() * self._weight_sum
        sum = 0
        for wname in self.weight:
            if a >= sum and a < sum + self.commands[wname].weight:
                return wname
            sum += self.commands[wname].weight
        raise ValueError

    class DoesNotFound(ValueError):
        pass


class DFA(object):
    """DFA(Deterministic Finite Automation) class.

    DFA drives all the combined states instance, and call the command
    instances according to their weights.
    
    Attributes
    :state (ro) - current state instance""" 

    def __init__(self, nexec=None, duration=None, **kwargv):
        """
        :nexec - the number of executed commands before DFA stopped.
        :duration - the duration of DFA runs before stopped.
        Either 'nexec' or 'duration' should be given.

        Other keyword arguments are taken as parameters for State instance."""

        self.nexec = nexec
        self.duration = duration
        self._state_params = kwargv
        self.states = {}
        self.state = None
        self._state_ret = None

    def add_state(self, state, *commands, **kwargv):
        """Add state into current DFA instance.
        
        :state - state is the State class.
        :commands - Any arguments following state are the command class.
        :is_start - boolean value, True means this state is "START" state in DFA.

        Other keyword arguments are taken as parameters for Command instance."""

        if not issubclass(state, State):
            raise ValueError
        sname = state.__name__.lower()
        self.states[sname] = state(self, **self._state_params)
        self.states[sname]._import_commands(*commands)

        if kwargv.pop('is_start', False):
            self.state = self.states[sname]

    def drive_machine(self):
        """Drive DFA machine.
        
        The DFA won't stop until time's up or reach the maximum execution."""

        if self.nexec is None and self.duration is None:
            raise ValueError
        if self.state is None:
            raise NotInitializedError

        if self.duration is None:
            self._drive_counter_machine()
        else:
            self._drive_time_machine()

    def _drive_time_machine(self):
        end_at = begin_at = time.time()
        while end_at - begin_at < self.duration:
            self._next_step()
            end_at = time.time()

    def _drive_counter_machine(self):
        count = 0
        while count < self.nexec:
            self._next_step()
            count += 1

    def _next_step(self):
        cname = self.state.choose()

        attr_list = dir(self.state)
        if 'before_%s' % cname in attr_list:
            getattr(self.state, 'before_%s' % cname)()

        self._state_ret = self.state.commands[cname].do(self._state_ret)

        if 'after_%s' % cname in attr_list:
            getattr(self.state, 'after_%s' % cname)()


class StateMachine(threading.Thread):
    """A Thread instance inherited from DFA"""

    def __init__(self, nexec=None, duration=None, **kwargv):
        """
        :nexec - the total numbers of command executions
        :duration - the time duration for DFA runs

        Other keyword arguments are taken as parameters for State instance."""

        super(StateMachine, self).__init__()
        self.dfa = DFA(nexec, duration, **kwargv)

    def add_state(self, state, *commands, **kwargv):
        self.dfa.add_state(state, *commands, **kwargv)

    def run(self):
        self.dfa.drive_machine()


class NotInitializedError(ValueError):
    """Error when DFA is not properly initialized."""

    pass

