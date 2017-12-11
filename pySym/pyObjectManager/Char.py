import z3
import ast
import logging
from .. import pyState

logger = logging.getLogger("ObjectManager:Char")

import os

class Char:
    """
    Define a Char (Character)
    """

    def __init__(self,varName,ctx,count=None,variable=None,state=None,increment=False,uuid=None):
        assert type(varName) is str, "Unexpected varName type of {}".format(type(varName))
        assert type(ctx) is int, "Unexpected ctx type of {}".format(type(ctx))
        assert type(count) in [int, type(None)], "Unexpected count type of {}".format(type(count))

        self.uuid = os.urandom(32) if uuid is None else uuid
        #self.size = 16 # TODO: This should probably be 8...
        self.state = state
        self.count = 0 if count is None else count
        self.varName = varName
        self.ctx = ctx
        #self.variable = BitVec('{1}{0}'.format(self.varName,self.count),ctx=self.ctx,size=self.size) if variable is None else variable
        self.variable = self.__make_variable() if variable is None else variable

        if state is not None:
            self.setState(state)

        if increment:
            self.increment()

    def __make_variable(self):
        return Int('{1}{0}'.format(self.varName,self.count),ctx=self.ctx,state=self.state)

    def __z3_bounds_constraint(self):
        """Returns the z3 bounds constraint for use in adding and removing it."""
        z3_obj = self.variable.getZ3Object() # This is hackish... But if I call my own getZ3Object it will recurse forever.
        return z3.And(z3_obj <= 0xff, z3_obj >= 0)

    def _add_variable_bounds(self):
        """Adds variable bounds to the solver for this Int to emulate a Char."""
        assert self.state is not None, "Char: Trying to add bounds without a state..."

        bounds = self.__z3_bounds_constraint()

        # If we're static, we don't need the bounds
        if self.isStatic():
            if bounds in self.state.solver.assertions():
                self.state.remove_constraints(bounds)

            return

        # If we don't already have those added, add them
        if bounds not in self.state.solver.assertions():
            self.state.addConstraint(bounds)


    def __deepcopy__(self,_):
        return self.copy()

    def __copy__(self):
        return self.copy()

    def copy(self):
        return Char(
            varName = self.varName,
            ctx = self.ctx,
            count = self.count,
            variable = self.variable.copy(),
            state = self.state if hasattr(self,"state") else None,
            uuid = self.uuid,
        )

    def __str__(self):
        return chr(int(self))

    def __int__(self):
        return self.state.any_int(self)

    def setTo(self,var):
        """
        Sets this Char to the variable. Raises exception on failure.
        """
        if type(var) not in [str, String, Char, Int]:
            err = "setTo: Invalid argument type {0}".format(type(var))
            logger.error(err)
            raise Exception(err)

        if (type(var) is String and var.length() != 1) or (type(var) is str and len(var) != 1):
            err = "setTo: Cannot set Char element to more than 1 length"
            logger.error(err)
            raise Exception(err)

        # We are becoming static
        if type(var) is str:
            # Remove our bounds constraints to help improve speed.
            self.state.remove_constraints(self.__z3_bounds_constraint())
            self.variable.setTo(ord(var))
        
        else:
            if type(var) is String:
                var = var[0]

            # Make sure we have our bounds set
            self._add_variable_bounds()
            
            # Remove our bounds constraints to help improve speed.
            if var.isStatic():
                self.state.remove_constraints(self.__z3_bounds_constraint())

            self.variable.setTo(var)


    def setState(self,state):
        """
        This is a bit strange, but State won't copy correctly due to Z3, so I need to bypass this a bit by setting State each time I copy
        """
        assert type(state) == pyState.State

        self.state = state
        self.variable.setState(state)

    def increment(self):
        self.count += 1
        self.variable = self.__make_variable()
        self._bounds_added = False

    
    def _isSame(self,**args):
        """
        Checks if variables for this object are the same as those entered.
        Assumes checks of type will be done prior to calling.
        """
        return True

    def getZ3Object(self):
        self._add_variable_bounds()
        return self.variable.getZ3Object()

    def isStatic(self):
        """
        Returns True if this object is a static variety (i.e.: "a").
        Also returns True if object has only one possibility
        """
        return self.variable.isStatic()
        #if len(self.state.any_n_int(self,2)) == 1:
        #    return True

        #return False

    def getValue(self):
        """
        Resolves the value of this Char. Assumes that isStatic method is called
        before this is called to ensure the value is not symbolic
        """
        #return chr(self.state.any_int(self))
        return chr(self.variable.getValue())


    def mustBe(self,var):
        """
        Return True if this Char must be equivalent to input (str/Char). False otherwise.
        """
        assert type(var) in [str, Char]
        
        # If we can't be, then mustBe is also False
        if not self.canBe(var):
            return False
        
        # Utilize the BitVec's methods here
        if type(var) is str:
            return self.variable.mustBe(ord(var))

        if type(var) is Char:
            return self.variable.mustBe(var.variable)        

        # If we can be, determine if this is the only option
        #if len(self.state.any_n_int(self,2)) == 1 and len(self.state.any_n_int(var,2)) == 1:
        #    return True
        
        # Looks like we're only one option
        return False


    def canBe(self,var):
        """
        Test if this Char can be equal to the given variable
        Returns True or False
        """

        assert type(var) in [str, Char]

        if type(var) is str and len(var) != 1:
            return False
        
        if type(var) is str:
            return self.variable.canBe(ord(var))
            #s = self.state.copy()
            #s.addConstraint(self.getZ3Object() == ord(var))
            #if s.isSat():
            #    return True
            #return False

        elif type(var) is Char:
            return self.variable.canBe(var.variable)
            #s = self.state.copy()
            #s.addConstraint(self.getZ3Object() == var.getZ3Object())
            #if s.isSat():
            #    return True
            #return False

    @property
    def is_unconstrained(self):
        """bool: Returns True if this Char has no external constraints applied to it. False otherwise."""
        
        # Consider it unconstrained if the only constraints are possibly the base ones that we have for Char
        return not z3Helpers.varIsUsedInSolver(var=self.getZ3Object(),solver=self.state.solver,ignore=self.__z3_bounds_constraint())

    @property
    def is_constrained(self):
        """bool: Opposite of is_unconstrained."""
        return not self.is_unconstrained


# Circular importing problem. Don't hate :-)
from .BitVec import BitVec
from .Int import Int
from .String import String
from ..pyState import z3Helpers
