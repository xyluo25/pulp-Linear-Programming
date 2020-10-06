# -*- coding: utf-8 -*-
"""

@author: Franco Peschiera

writeMPS adapted from Julian Märte (https://github.com/pchtsp/pysmps)
"""

import re
from . import constants as const

CORE_FILE_ROW_MODE = "ROWS"
CORE_FILE_COL_MODE = "COLUMNS"
CORE_FILE_RHS_MODE = "RHS"
CORE_FILE_BOUNDS_MODE = "BOUNDS"

CORE_FILE_BOUNDS_MODE_NAME_GIVEN = "BOUNDS_NAME"
CORE_FILE_BOUNDS_MODE_NO_NAME = "BOUNDS_NO_NAME"
CORE_FILE_RHS_MODE_NAME_GIVEN = "RHS_NAME"
CORE_FILE_RHS_MODE_NO_NAME = "RHS_NO_NAME"

ROW_MODE_OBJ = "N"

BOUNDS_EQUIV = dict(LO='lowBound', UP='upBound')

ROW_EQUIV = {v: k for k, v in const.LpConstraintTypeToMps.items()}
COL_EQUIV = {1: 'Integer', 0: 'Continuous'}
ROW_DEFAULT = dict(pi=None, constant=0)
COL_DEFAULT = dict(lowBound=0, upBound=None, varValue=None, dj=None)


def readMPS(path, sense, drop_constraint_names=False):
    mode = ""
    parameters = dict(name='', sense=sense, status=0, sol_status=0)
    variable_info = {}
    constraints = {}
    objective = dict(name='', coefficients=[])
    # TODO: sos1 and sos2
    sos1 = []
    sos2 = []
    # TODO: maybe take out rhs_names and bnd_names
    rhs_names = []
    bnd_names = []
    integral_marker = False
    
    with open(path, "r") as reader:
        for line in reader:
            line = re.split(" |\t", line)
            line = [x.strip() for x in line]
            line = list(filter(None, line))
            
            if line[0] == "ENDATA":
                break
            if line[0] == "*":
                continue
            if line[0] == "NAME":
                parameters['name'] = line[1]
                continue

            # here we get the mode
            if line[0] in [CORE_FILE_ROW_MODE, CORE_FILE_COL_MODE]:
                mode = line[0]
            elif line[0] == CORE_FILE_RHS_MODE and len(line) <= 2:
                if len(line) > 1:
                    rhs_names.append(line[1])
                    mode = CORE_FILE_RHS_MODE_NAME_GIVEN
                else:
                    mode = CORE_FILE_RHS_MODE_NO_NAME
            elif line[0] == CORE_FILE_BOUNDS_MODE and len(line) <= 2:
                if len(line) > 1:
                    bnd_names.append(line[1])
                    mode = CORE_FILE_BOUNDS_MODE_NAME_GIVEN
                else:
                    mode = CORE_FILE_BOUNDS_MODE_NO_NAME

            # here we query the mode variable
            elif mode == CORE_FILE_ROW_MODE:
                row_type = line[0]
                row_name = line[1]
                if row_type == ROW_MODE_OBJ:
                    objective['name'] = row_name
                else:
                    constraints[row_name] = \
                        dict(sense=ROW_EQUIV[row_type], name=row_name, coefficients=[], **ROW_DEFAULT)
            elif mode == CORE_FILE_COL_MODE:
                var_name = line[0]
                if len(line) > 1 and line[1] == "'MARKER'":
                    if line[2] == "'INTORG'":
                        integral_marker = True
                    elif line[2] == "'INTEND'":
                        integral_marker = False
                    continue
                if var_name not in variable_info:
                    variable_info[var_name] = \
                        dict(cat=COL_EQUIV[integral_marker], name=var_name, **COL_DEFAULT)
                j = 1
                while j < len(line) - 1:
                    if line[j] == objective['name']:
                        # we store the variable objective coefficient
                        objective['coefficients'].append(dict(name=var_name, value=float(line[j + 1])))
                    else:
                        # we store the variable coefficient
                        constraints[line[j]]['coefficients'].append(dict(name=var_name, value=float(line[j + 1])))
                    j = j + 2
            elif mode == CORE_FILE_RHS_MODE_NAME_GIVEN:
                if line[0] != rhs_names[-1]:
                    raise Exception("Other RHS name was given even though name was set after RHS tag.")
                set_rhs(line, constraints)
            elif mode == CORE_FILE_RHS_MODE_NO_NAME:
                set_rhs(line, constraints)
                if line[0] not in rhs_names:
                    rhs_names.append(line[0])
            elif mode == CORE_FILE_BOUNDS_MODE_NAME_GIVEN:
                if line[1] != bnd_names[-1]:
                    raise Exception("Other BOUNDS name was given even though name was set after BOUNDS tag.")
                set_bounds(line, variable_info)
            elif mode == CORE_FILE_BOUNDS_MODE_NO_NAME:
                set_bounds(line, variable_info)
                if line[1] not in bnd_names:
                    bnd_names.append(line[1])
    constraints = list(constraints.values())
    if drop_constraint_names:
        for c in constraints:
            c['name'] = None
        objective['name'] = None
    variable_info = list(variable_info.values())
    return dict(parameters=parameters,
                objective=objective,
                variables=variable_info,
                constraints=constraints,
                sos1=sos1,
                sos2=sos2)


def set_bounds(line, variable_dict):
    bound = line[0]
    var_name = line[2]

    def set_one_bound(bound_type, value):
        variable_dict[var_name][BOUNDS_EQUIV[bound_type]] = value

    def set_both_bounds(value_low, value_up):
        set_one_bound('LO', value_low)
        set_one_bound('UP', value_up)

    if bound == "FR":
        set_both_bounds(None, None)
        return
    elif bound == 'BV':
        set_both_bounds(0, 1)
        return
    value = float(line[3])
    if bound in ["LO", "UP"]:
        set_one_bound(bound, value)
    elif bound == "FX":
        set_both_bounds(value, value)
    return


def set_rhs(line, constraints_dict):
    constraints_dict[line[1]]['constant'] = - float(line[2])
    return


def writeMPS(LpProblem, filename, mpsSense = 0, rename = 0, mip = 1):
        wasNone, dummyVar = LpProblem.fixObjective()
        if mpsSense == 0: mpsSense = LpProblem.sense
        cobj = LpProblem.objective
        if mpsSense != LpProblem.sense:
            n = cobj.name
            cobj = - cobj
            cobj.name = n
        if rename:
            constrNames, varNames, cobj.name = LpProblem.normalisedNames()
            # No need to call self.variables() again, we have just filled self._variables:
            vs = LpProblem._variables
        else:
            vs = LpProblem.variables()
            varNames = dict((v.name, v.name) for v in vs)
            constrNames = dict((c, c) for c in LpProblem.constraints)
        model_name = LpProblem.name
        if rename:
            model_name = "MODEL"
        objName = cobj.name
        if not objName:
            objName = "OBJ"

        # constraints
        row_lines = [" " + const.LpConstraintTypeToMps[c.sense] + "  " + constrNames[k] + "\n"
                     for k, c in LpProblem.constraints.items()]
        # Creation of a dict of dict:
        # coefs[variable_name][constraint_name] = coefficient
        coefs = {varNames[v.name]: {} for v in vs}
        for k, c in LpProblem.constraints.items():
            k = constrNames[k]
            for v, value in c.items():
                coefs[varNames[v.name]][k] = value

        # matrix
        columns_lines = []
        for v in vs:
            name = varNames[v.name]
            columns_lines.extend(MPSColumnLines(coefs[name], v, mip, name, cobj, objName))

        # right hand side
        rhs_lines = ["    RHS       %-8s  % .12e\n" % (constrNames[k], -c.constant if c.constant != 0 else 0)
                     for k, c in LpProblem.constraints.items()]
        # bounds
        bound_lines = []
        for v in vs:
            bound_lines.extend(MPSBoundLines(varNames[v.name], v, mip))

        with open(filename, "w") as f:
            f.write("*SENSE:"+ const.LpSenses[mpsSense]+"\n")
            f.write("NAME          " + model_name + "\n")
            f.write("ROWS\n")
            f.write(" N  %s\n" % objName)
            f.write(''.join(row_lines))
            f.write("COLUMNS\n")
            f.write(''.join(columns_lines))
            f.write("RHS\n")
            f.write(''.join(rhs_lines))
            f.write("BOUNDS\n")
            f.write(''.join(bound_lines))
            f.write("ENDATA\n")
        LpProblem.restoreObjective(wasNone, dummyVar)
        # returns the variables, in writing order
        if rename == 0:
            return vs
        else:
            return vs, varNames, constrNames, cobj.name


def MPSColumnLines(cv, variable, mip, name, cobj, objName):
    columns_lines = []
    if mip and variable.cat == const.LpInteger:
        columns_lines.append("    MARK      'MARKER'                 'INTORG'\n")
    # Most of the work is done here
    _tmp = ["    %-8s  %-8s  % .12e\n" % (name, k, v) for k, v in cv.items()]
    columns_lines.extend(_tmp)

    # objective function
    if variable in cobj:
        columns_lines.append("    %-8s  %-8s  % .12e\n" % (name, objName, cobj[variable]))
    if mip and variable.cat == const.LpInteger:
        columns_lines.append("    MARK      'MARKER'                 'INTEND'\n")
    return columns_lines


def MPSBoundLines(name, variable, mip):
    if variable.lowBound is not None and variable.lowBound == variable.upBound:
        return [" FX BND       %-8s  % .12e\n" % (name, variable.lowBound)]
    elif variable.lowBound == 0 and variable.upBound == 1 and mip and variable.cat == const.LpInteger:
        return [" BV BND       %-8s\n" % name]
    bound_lines = []
    if variable.lowBound is not None:
        # In MPS files, variables with no bounds (i.e. >= 0)
        # are assumed BV by COIN and CPLEX.
        # So we explicitly write a 0 lower bound in this case.
        if variable.lowBound != 0 or (mip and variable.cat == const.LpInteger and variable.upBound is None):
            bound_lines.append(" LO BND       %-8s  % .12e\n" % (name, variable.lowBound))
    else:
        if variable.upBound is not None:
            bound_lines.append(" MI BND       %-8s\n" % name)
        else:
            bound_lines.append(" FR BND       %-8s\n" % name)
    if variable.upBound is not None:
        bound_lines.append(" UP BND       %-8s  % .12e\n" % (name, variable.upBound))
    return bound_lines


def writeLP(self, filename, writeSOS = 1, mip = 1, max_length=100):
    f = open(filename, "w")
    f.write("\\* " + self.name + " *\\\n")
    if self.sense == 1:
        f.write("Minimize\n")
    else:
        f.write("Maximize\n")
    wasNone, objectiveDummyVar = self.fixObjective()
    objName = self.objective.name
    if not objName: objName = "OBJ"
    f.write(self.objective.asCplexLpAffineExpression(objName, constant=0))
    f.write("Subject To\n")
    ks = list(self.constraints.keys())
    ks.sort()
    dummyWritten = False
    for k in ks:
        constraint = self.constraints[k]
        if not list(constraint.keys()):
            # empty constraint add the dummyVar
            dummyVar = self.get_dummyVar()
            constraint += dummyVar
            # set this dummyvar to zero so infeasible problems are not made feasible
            if not dummyWritten:
                f.write((dummyVar == 0.0).asCplexLpConstraint("_dummy"))
                dummyWritten = True
        f.write(constraint.asCplexLpConstraint(k))
    # check if any names are longer than 100 characters
    self.checkLengthVars(max_length)
    vs = self.variables()
    # check for repeated names
    self.checkDuplicateVars()
    # Bounds on non-"positive" variables
    # Note: XPRESS and CPLEX do not interpret integer variables without
    # explicit bounds
    if mip:
        vg = [v for v in vs if not (v.isPositive() and v.cat == const.LpContinuous) \
              and not v.isBinary()]
    else:
        vg = [v for v in vs if not v.isPositive()]
    if vg:
        f.write("Bounds\n")
        for v in vg:
            f.write("%s\n" % v.asCplexLpVariable())
    # Integer non-binary variables
    if mip:
        vg = [v for v in vs if v.cat == const.LpInteger and not v.isBinary()]
        if vg:
            f.write("Generals\n")
            for v in vg: f.write("%s\n" % v.name)
        # Binary variables
        vg = [v for v in vs if v.isBinary()]
        if vg:
            f.write("Binaries\n")
            for v in vg: f.write("%s\n" % v.name)
    # Special Ordered Sets
    if writeSOS and (self.sos1 or self.sos2):
        f.write("SOS\n")
        if self.sos1:
            for sos in self.sos1.values():
                f.write("S1:: \n")
                for v, val in sos.items():
                    f.write(" %s: %.12g\n" % (v.name, val))
        if self.sos2:
            for sos in self.sos2.values():
                f.write("S2:: \n")
                for v, val in sos.items():
                    f.write(" %s: %.12g\n" % (v.name, val))
    f.write("End\n")
    f.close()
    self.restoreObjective(wasNone, objectiveDummyVar)
    return vs