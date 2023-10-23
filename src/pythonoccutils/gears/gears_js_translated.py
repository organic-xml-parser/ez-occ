from js2py.pyjs import *
# setting scope
var = Scope( JS_BUILTINS )
set_global_object(var)

# Code follows:
var.registers(['involuteBezCoeffs', '_toConsumableArray', 'createIntGearTooth', 'createIntGearOutline', 'createGearTooth', 'createGearOutline'])
@Js
def PyJsHoisted__toConsumableArray_(arr, this, arguments, var=var):
    var = Scope({'arr':arr, 'this':this, 'arguments':arguments}, var)
    var.registers(['arr2', 'arr', 'i'])
    if var.get('Array').callprop('isArray', var.get('arr')):
        #for JS loop
        var.put('i', Js(0.0))
        var.put('arr2', var.get('Array')(var.get('arr').get('length')))
        while (var.get('i')<var.get('arr').get('length')):
            var.get('arr2').put(var.get('i'), var.get('arr').get(var.get('i')))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        return var.get('arr2')
    else:
        return var.get('Array').callprop('from', var.get('arr'))
PyJsHoisted__toConsumableArray_.func_name = '_toConsumableArray'
var.put('_toConsumableArray', PyJsHoisted__toConsumableArray_)
Js('use strict')
pass
pass
@Js
def PyJs_anonymous_0_(this, arguments, var=var):
    var = Scope({'this':this, 'arguments':arguments}, var)
    var.registers(['rotateTooth', 'rotate', 'genInvolutePolar', 'genGearToothData', 'genIntGearToothData', 'toCartesian'])
    @Js
    def PyJsHoisted_rotate_(pt, rads, this, arguments, var=var):
        var = Scope({'pt':pt, 'rads':rads, 'this':this, 'arguments':arguments}, var)
        var.registers(['rads', 'sinA', 'cosA', 'pt'])
        var.put('sinA', var.get('Math').callprop('sin', var.get('rads')))
        var.put('cosA', var.get('Math').callprop('cos', var.get('rads')))
        return Js({'x':((var.get('pt').get('x')*var.get('cosA'))-(var.get('pt').get('y')*var.get('sinA'))),'y':((var.get('pt').get('x')*var.get('sinA'))+(var.get('pt').get('y')*var.get('cosA')))})
    PyJsHoisted_rotate_.func_name = 'rotate'
    var.put('rotate', PyJsHoisted_rotate_)
    @Js
    def PyJsHoisted_toCartesian_(radius, angle, this, arguments, var=var):
        var = Scope({'radius':radius, 'angle':angle, 'this':this, 'arguments':arguments}, var)
        var.registers(['angle', 'radius'])
        return Js({'x':(var.get('radius')*var.get('Math').callprop('cos', var.get('angle'))),'y':(var.get('radius')*var.get('Math').callprop('sin', var.get('angle')))})
    PyJsHoisted_toCartesian_.func_name = 'toCartesian'
    var.put('toCartesian', PyJsHoisted_toCartesian_)
    @Js
    def PyJsHoisted_genInvolutePolar_(Rb, R, this, arguments, var=var):
        var = Scope({'Rb':Rb, 'R':R, 'this':this, 'arguments':arguments}, var)
        var.registers(['Rb', 'R'])
        return ((var.get('Math').callprop('sqrt', ((var.get('R')*var.get('R'))-(var.get('Rb')*var.get('Rb'))))/var.get('Rb'))-var.get('Math').callprop('acos', (var.get('Rb')/var.get('R'))))
    PyJsHoisted_genInvolutePolar_.func_name = 'genInvolutePolar'
    var.put('genInvolutePolar', PyJsHoisted_genInvolutePolar_)
    @Js
    def PyJsHoisted_genGearToothData_(m, Z, phi, this, arguments, var=var):
        var = Scope({'m':m, 'Z':Z, 'phi':phi, 'this':this, 'arguments':arguments}, var)
        var.registers(['Ra', 'pt', 'invR', 'clearance', 'filletNext', 'addBz', 'fm', 'fe', 'i', 'Rpitch', 'Rb', 'fs', 'fillet', 'pitchAngle', 'fRad', 'data', 'pitchToFilletAngle', 'filletR', 'dedendum', 'dedBz', 'rootR', 'Rroot', 'addendum', 'baseToPitchAngle', 'inv', 'rootNext', 'Z', 'phi', 'Rf', 'm', 'filletAngle'])
        var.put('addendum', var.get('m'))
        var.put('dedendum', (Js(1.25)*var.get('m')))
        var.put('clearance', (var.get('dedendum')-var.get('addendum')))
        var.put('Rpitch', ((var.get('Z')*var.get('m'))/Js(2.0)))
        var.put('Rb', (var.get('Rpitch')*var.get('Math').callprop('cos', ((var.get('phi')*var.get('Math').get('PI'))/Js(180.0)))))
        var.put('Ra', (var.get('Rpitch')+var.get('addendum')))
        var.put('Rroot', (var.get('Rpitch')-var.get('dedendum')))
        var.put('fRad', (Js(1.5)*var.get('clearance')))
        var.put('pitchAngle', ((Js(2.0)*var.get('Math').get('PI'))/var.get('Z')))
        var.put('baseToPitchAngle', var.get('genInvolutePolar')(var.get('Rb'), var.get('Rpitch')))
        var.put('pitchToFilletAngle', var.get('baseToPitchAngle'))
        var.put('filletAngle', var.get('Math').callprop('atan', (var.get('fRad')/(var.get('fRad')+var.get('Rroot')))))
        var.put('Rf', var.get('Math').callprop('sqrt', (((var.get('Rroot')+var.get('fRad'))*(var.get('Rroot')+var.get('fRad')))-(var.get('fRad')*var.get('fRad')))))
        if (var.get('Rb')<var.get('Rf')):
            var.put('Rf', (var.get('Rroot')+var.get('clearance')))
        if (var.get('Rf')>var.get('Rb')):
            var.put('pitchToFilletAngle', var.get('genInvolutePolar')(var.get('Rb'), var.get('Rf')), '-')
        var.put('fe', Js(1.0))
        var.put('fs', Js(0.01))
        if (var.get('Rf')>var.get('Rb')):
            var.put('fs', (((var.get('Rf')*var.get('Rf'))-(var.get('Rb')*var.get('Rb')))/((var.get('Ra')*var.get('Ra'))-(var.get('Rb')*var.get('Rb')))))
        var.put('fm', (var.get('fs')+((var.get('fe')-var.get('fs'))/Js(4.0))))
        var.put('dedBz', var.get('involuteBezCoeffs')(var.get('m'), var.get('Z'), var.get('phi'), Js(3.0), var.get('fs'), var.get('fm')))
        var.put('addBz', var.get('involuteBezCoeffs')(var.get('m'), var.get('Z'), var.get('phi'), Js(3.0), var.get('fm'), var.get('fe')))
        var.put('inv', var.get('dedBz').callprop('concat', var.get('addBz').callprop('slice', Js(1.0))))
        var.put('invR', Js([]))
        #for JS loop
        var.put('i', Js(0.0))
        while (var.get('i')<var.get('inv').get('length')):
            var.put('pt', var.get('rotate')(var.get('inv').get(var.get('i')), ((-var.get('baseToPitchAngle'))-(var.get('pitchAngle')/Js(4.0)))))
            var.get('inv').put(var.get('i'), var.get('pt'))
            var.get('invR').put(var.get('i'), Js({'x':var.get('pt').get('x'),'y':(-var.get('pt').get('y'))}))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        var.put('fillet', var.get('toCartesian')(var.get('Rf'), (((-var.get('pitchAngle'))/Js(4.0))-var.get('pitchToFilletAngle'))))
        var.put('filletR', Js({'x':var.get('fillet').get('x'),'y':(-var.get('fillet').get('y'))}))
        var.put('rootR', var.get('toCartesian')(var.get('Rroot'), (((var.get('pitchAngle')/Js(4.0))+var.get('pitchToFilletAngle'))+var.get('filletAngle'))))
        var.put('rootNext', var.get('toCartesian')(var.get('Rroot'), ((((Js(3.0)*var.get('pitchAngle'))/Js(4.0))-var.get('pitchToFilletAngle'))-var.get('filletAngle'))))
        var.put('filletNext', var.get('rotate')(var.get('fillet'), var.get('pitchAngle')))
        var.put('data', Js([]))
        var.get('data').callprop('push', Js('M'), var.get('fillet'))
        if (var.get('Rf')<var.get('Rb')):
            var.get('data').callprop('push', Js('L'), var.get('inv').get('0'))
        var.get('data').callprop('push', Js('C'), var.get('inv').get('1'), var.get('inv').get('2'), var.get('inv').get('3'), var.get('inv').get('4'), var.get('inv').get('5'), var.get('inv').get('6'))
        var.get('data').callprop('push', Js('A'), var.get('Ra'), var.get('Ra'), Js(0.0), Js(0.0), Js(1.0), var.get('invR').get('6'))
        var.get('data').callprop('push', Js('C'), var.get('invR').get('5'), var.get('invR').get('4'), var.get('invR').get('3'), var.get('invR').get('2'), var.get('invR').get('1'), var.get('invR').get('0'))
        if (var.get('Rf')<var.get('Rb')):
            var.get('data').callprop('push', Js('L'), var.get('filletR'))
        if (var.get('rootNext').get('y')>var.get('rootR').get('y')):
            var.get('data').callprop('push', Js('A'), var.get('fRad'), var.get('fRad'), Js(0.0), Js(0.0), Js(0.0), var.get('rootR'))
            var.get('data').callprop('push', Js('A'), var.get('Rroot'), var.get('Rroot'), Js(0.0), Js(0.0), Js(1.0), var.get('rootNext'))
        var.get('data').callprop('push', Js('A'), var.get('fRad'), var.get('fRad'), Js(0.0), Js(0.0), Js(0.0), var.get('filletNext'))
        return var.get('data')
    PyJsHoisted_genGearToothData_.func_name = 'genGearToothData'
    var.put('genGearToothData', PyJsHoisted_genGearToothData_)
    @Js
    def PyJsHoisted_genIntGearToothData_(m, Z, phi, this, arguments, var=var):
        var = Scope({'m':m, 'Z':Z, 'phi':phi, 'this':this, 'arguments':arguments}, var)
        var.registers(['Ra', 'pt', 'invR', 'clearance', 'tipR', 'filletNext', 'tip', 'addBz', 'fm', 'fe', 'i', 'Rpitch', 'Rb', 'fs', 'fillet', 'pitchAngle', 'fRad', 'tipToPitchAngle', 'data', 'pitchToFilletAngle', 'dedendum', 'dedBz', 'rootR', 'Rroot', 'addendum', 'baseToPitchAngle', 'inv', 'rootNext', 'Z', 'phi', 'Rf', 'm', 'filletAngle'])
        var.put('addendum', (Js(0.6)*var.get('m')))
        var.put('dedendum', (Js(1.25)*var.get('m')))
        var.put('Rpitch', ((var.get('Z')*var.get('m'))/Js(2.0)))
        var.put('Rb', (var.get('Rpitch')*var.get('Math').callprop('cos', ((var.get('phi')*var.get('Math').get('PI'))/Js(180.0)))))
        var.put('Ra', (var.get('Rpitch')-var.get('addendum')))
        var.put('Rroot', (var.get('Rpitch')+var.get('dedendum')))
        var.put('clearance', (Js(0.25)*var.get('m')))
        var.put('Rf', (var.get('Rroot')-var.get('clearance')))
        var.put('fRad', (Js(1.5)*var.get('clearance')))
        var.put('pitchAngle', ((Js(2.0)*var.get('Math').get('PI'))/var.get('Z')))
        var.put('baseToPitchAngle', var.get('genInvolutePolar')(var.get('Rb'), var.get('Rpitch')))
        var.put('tipToPitchAngle', var.get('baseToPitchAngle'))
        if (var.get('Ra')>var.get('Rb')):
            var.put('tipToPitchAngle', var.get('genInvolutePolar')(var.get('Rb'), var.get('Ra')), '-')
        var.put('pitchToFilletAngle', (var.get('genInvolutePolar')(var.get('Rb'), var.get('Rf'))-var.get('baseToPitchAngle')))
        var.put('filletAngle', ((Js(1.414)*var.get('clearance'))/var.get('Rf')))
        var.put('fe', Js(1.0))
        var.put('fs', Js(0.01))
        if (var.get('Ra')>var.get('Rb')):
            var.put('fs', (((var.get('Ra')*var.get('Ra'))-(var.get('Rb')*var.get('Rb')))/((var.get('Rf')*var.get('Rf'))-(var.get('Rb')*var.get('Rb')))))
        var.put('fm', (var.get('fs')+((var.get('fe')-var.get('fs'))/Js(4.0))))
        var.put('addBz', var.get('involuteBezCoeffs')(var.get('m'), var.get('Z'), var.get('phi'), Js(3.0), var.get('fs'), var.get('fm')))
        var.put('dedBz', var.get('involuteBezCoeffs')(var.get('m'), var.get('Z'), var.get('phi'), Js(3.0), var.get('fm'), var.get('fe')))
        var.put('invR', var.get('addBz').callprop('concat', var.get('dedBz').callprop('slice', Js(1.0))))
        var.put('inv', Js([]))
        #for JS loop
        var.put('i', Js(0.0))
        while (var.get('i')<var.get('invR').get('length')):
            var.put('pt', var.get('rotate')(var.get('invR').get(var.get('i')), ((var.get('pitchAngle')/Js(4.0))-var.get('baseToPitchAngle'))))
            var.get('invR').put(var.get('i'), var.get('pt'))
            var.get('inv').put(var.get('i'), Js({'x':var.get('pt').get('x'),'y':(-var.get('pt').get('y'))}))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        var.put('fillet', Js({'x':var.get('inv').get('6').get('x'),'y':var.get('inv').get('6').get('y')}))
        var.put('tip', var.get('toCartesian')(var.get('Ra'), (((-var.get('pitchAngle'))/Js(4.0))+var.get('tipToPitchAngle'))))
        var.put('tipR', Js({'x':var.get('tip').get('x'),'y':(-var.get('tip').get('y'))}))
        var.put('rootR', var.get('toCartesian')(var.get('Rroot'), (((var.get('pitchAngle')/Js(4.0))+var.get('pitchToFilletAngle'))+var.get('filletAngle'))))
        var.put('rootNext', var.get('toCartesian')(var.get('Rroot'), ((((Js(3.0)*var.get('pitchAngle'))/Js(4.0))-var.get('pitchToFilletAngle'))-var.get('filletAngle'))))
        var.put('filletNext', var.get('rotate')(var.get('fillet'), var.get('pitchAngle')))
        var.put('data', Js([]))
        var.get('data').callprop('push', Js('M'), var.get('inv').get('6'))
        var.get('data').callprop('push', Js('C'), var.get('inv').get('5'), var.get('inv').get('4'), var.get('inv').get('3'), var.get('inv').get('2'), var.get('inv').get('1'), var.get('inv').get('0'))
        if (var.get('Ra')<var.get('Rb')):
            var.get('data').callprop('push', Js('L'), var.get('tip'))
        var.get('data').callprop('push', Js('A'), var.get('Ra'), var.get('Ra'), Js(0.0), Js(0.0), Js(1.0), var.get('tipR'))
        if (var.get('Ra')<var.get('Rb')):
            var.get('data').callprop('push', Js('L'), var.get('invR').get('0'))
        var.get('data').callprop('push', Js('C'), var.get('invR').get('1'), var.get('invR').get('2'), var.get('invR').get('3'), var.get('invR').get('4'), var.get('invR').get('5'), var.get('invR').get('6'))
        if (var.get('rootR').get('y')<var.get('rootNext').get('y')):
            var.get('data').callprop('push', Js('A'), var.get('fRad'), var.get('fRad'), Js(0.0), Js(0.0), Js(1.0), var.get('rootR'))
            var.get('data').callprop('push', Js('A'), var.get('Rroot'), var.get('Rroot'), Js(0.0), Js(0.0), Js(1.0), var.get('rootNext'))
        var.get('data').callprop('push', Js('A'), var.get('fRad'), var.get('fRad'), Js(0.0), Js(0.0), Js(1.0), var.get('filletNext'))
        return var.get('data')
    PyJsHoisted_genIntGearToothData_.func_name = 'genIntGearToothData'
    var.put('genIntGearToothData', PyJsHoisted_genIntGearToothData_)
    @Js
    def PyJsHoisted_rotateTooth_(inData, rotRads, this, arguments, var=var):
        var = Scope({'inData':inData, 'rotRads':rotRads, 'this':this, 'arguments':arguments}, var)
        var.registers(['outData', 'rotRads', 'i', 'pt', 'rot', 'inData'])
        var.put('rot', (var.get('rotRads') or Js(0.0)))
        var.put('outData', Js([]))
        #for JS loop
        var.put('i', Js(0.0))
        while (var.get('i')<var.get('inData').get('length')):
            if PyJsStrictNeq(var.get('inData').get(var.get('i')).get('x'),var.get('undefined')):
                var.put('pt', var.get('rotate')(var.get('inData').get(var.get('i')), var.get('rot')))
                var.get('outData').callprop('push', var.get('pt').get('x'), var.get('pt').get('y'))
            else:
                var.get('outData').callprop('push', var.get('inData').get(var.get('i')))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        return var.get('outData')
    PyJsHoisted_rotateTooth_.func_name = 'rotateTooth'
    var.put('rotateTooth', PyJsHoisted_rotateTooth_)
    Js('use strict')
    @Js
    def PyJs_involuteBezCoeffs_1_(module, numTeeth, pressureAngle, order, fstart, fstop, this, arguments, var=var):
        var = Scope({'module':module, 'numTeeth':numTeeth, 'pressureAngle':pressureAngle, 'order':order, 'fstart':fstart, 'fstop':fstop, 'this':this, 'arguments':arguments, 'involuteBezCoeffs':PyJs_involuteBezCoeffs_1_}, var)
        var.registers(['module', 'ta', 'Ra', 'numTeeth', 'involuteYbez', 'i', 'Rpitch', 'PI', 'Rb', 'bzCoeffs', 'p', 'chebyPolyCoeffs', 'ts', 'chebyExpnCoeffs', 'fstart', 'pressureAngle', 'fstop', 'binom', 'te', 'involuteXbez', 'phi', 'order', 'stop', 'bcoeff', 'start', 'bezCoeff'])
        @Js
        def PyJsHoisted_chebyExpnCoeffs_(j, func, this, arguments, var=var):
            var = Scope({'j':j, 'func':func, 'this':this, 'arguments':arguments}, var)
            var.registers(['j', 'c', 'N', 'k', 'func'])
            var.put('N', Js(50.0))
            var.put('c', Js(0.0))
            #for JS loop
            var.put('k', Js(1.0))
            while (var.get('k')<=var.get('N')):
                var.put('c', (var.get('func')(var.get('Math').callprop('cos', ((var.get('PI')*(var.get('k')-Js(0.5)))/var.get('N'))))*var.get('Math').callprop('cos', (((var.get('PI')*var.get('j'))*(var.get('k')-Js(0.5)))/var.get('N')))), '+')
                # update
                (var.put('k',Js(var.get('k').to_number())+Js(1))-Js(1))
            return ((Js(2.0)*var.get('c'))/var.get('N'))
        PyJsHoisted_chebyExpnCoeffs_.func_name = 'chebyExpnCoeffs'
        var.put('chebyExpnCoeffs', PyJsHoisted_chebyExpnCoeffs_)
        @Js
        def PyJsHoisted_chebyPolyCoeffs_(p, func, this, arguments, var=var):
            var = Scope({'p':p, 'func':func, 'this':this, 'arguments':arguments}, var)
            var.registers(['pwr', 'j', 'p', 'fnCoeff', 'i', 'T', 'coeffs', 'k', 'func'])
            var.put('coeffs', Js([]))
            var.put('fnCoeff', Js([]))
            var.put('T', Js([Js([]), Js([])]))
            #for JS loop
            var.put('i', Js(0.0))
            while (var.get('i')<(var.get('p')+Js(1.0))):
                var.get('T').get('0').put(var.get('i'), Js(0.0))
                var.get('T').get('1').put(var.get('i'), Js(0.0))
                # update
                (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
            var.get('T').get('0').put('0', Js(1.0))
            var.get('T').get('1').put('1', Js(1.0))
            #for JS loop
            var.put('k', Js(1.0))
            while (var.get('k')<(var.get('p')+Js(1.0))):
                var.get('T').put((var.get('k')+Js(1.0)), Js([Js(0.0)]))
                #for JS loop
                var.put('j', Js(0.0))
                while (var.get('j')<(var.get('T').get(var.get('k')).get('length')-Js(1.0))):
                    var.get('T').get((var.get('k')+Js(1.0))).put((var.get('j')+Js(1.0)), (Js(2.0)*var.get('T').get(var.get('k')).get(var.get('j'))))
                    # update
                    (var.put('j',Js(var.get('j').to_number())+Js(1))-Js(1))
                #for JS loop
                var.put('j', Js(0.0))
                while (var.get('j')<var.get('T').get((var.get('k')-Js(1.0))).get('length')):
                    var.get('T').get((var.get('k')+Js(1.0))).put(var.get('j'), var.get('T').get((var.get('k')-Js(1.0))).get(var.get('j')), '-')
                    # update
                    (var.put('j',Js(var.get('j').to_number())+Js(1))-Js(1))
                # update
                (var.put('k',Js(var.get('k').to_number())+Js(1))-Js(1))
            #for JS loop
            var.put('k', Js(0.0))
            while (var.get('k')<=var.get('p')):
                var.get('fnCoeff').put(var.get('k'), var.get('chebyExpnCoeffs')(var.get('k'), var.get('func')))
                var.get('coeffs').put(var.get('k'), Js(0.0))
                # update
                (var.put('k',Js(var.get('k').to_number())+Js(1))-Js(1))
            #for JS loop
            var.put('k', Js(0.0))
            while (var.get('k')<=var.get('p')):
                #for JS loop
                var.put('pwr', Js(0.0))
                while (var.get('pwr')<=var.get('p')):
                    var.get('coeffs').put(var.get('pwr'), (var.get('fnCoeff').get(var.get('k'))*var.get('T').get(var.get('k')).get(var.get('pwr'))), '+')
                    # update
                    (var.put('pwr',Js(var.get('pwr').to_number())+Js(1))-Js(1))
                # update
                (var.put('k',Js(var.get('k').to_number())+Js(1))-Js(1))
            var.get('coeffs').put('0', (var.get('chebyExpnCoeffs')(Js(0.0), var.get('func'))/Js(2.0)), '-')
            return var.get('coeffs')
        PyJsHoisted_chebyPolyCoeffs_.func_name = 'chebyPolyCoeffs'
        var.put('chebyPolyCoeffs', PyJsHoisted_chebyPolyCoeffs_)
        @Js
        def PyJsHoisted_involuteXbez_(t, this, arguments, var=var):
            var = Scope({'t':t, 'this':this, 'arguments':arguments}, var)
            var.registers(['t', 'theta', 'x'])
            var.put('x', ((var.get('t')*Js(2.0))-Js(1.0)))
            var.put('theta', (((var.get('x')*(var.get('te')-var.get('ts')))/Js(2.0))+((var.get('ts')+var.get('te'))/Js(2.0))))
            return (var.get('Rb')*(var.get('Math').callprop('cos', var.get('theta'))+(var.get('theta')*var.get('Math').callprop('sin', var.get('theta')))))
        PyJsHoisted_involuteXbez_.func_name = 'involuteXbez'
        var.put('involuteXbez', PyJsHoisted_involuteXbez_)
        @Js
        def PyJsHoisted_involuteYbez_(t, this, arguments, var=var):
            var = Scope({'t':t, 'this':this, 'arguments':arguments}, var)
            var.registers(['t', 'theta', 'x'])
            var.put('x', ((var.get('t')*Js(2.0))-Js(1.0)))
            var.put('theta', (((var.get('x')*(var.get('te')-var.get('ts')))/Js(2.0))+((var.get('ts')+var.get('te'))/Js(2.0))))
            return (var.get('Rb')*(var.get('Math').callprop('sin', var.get('theta'))-(var.get('theta')*var.get('Math').callprop('cos', var.get('theta')))))
        PyJsHoisted_involuteYbez_.func_name = 'involuteYbez'
        var.put('involuteYbez', PyJsHoisted_involuteYbez_)
        @Js
        def PyJsHoisted_binom_(n, k, this, arguments, var=var):
            var = Scope({'n':n, 'k':k, 'this':this, 'arguments':arguments}, var)
            var.registers(['n', 'coeff', 'k', 'i'])
            var.put('coeff', Js(1.0))
            #for JS loop
            var.put('i', ((var.get('n')-var.get('k'))+Js(1.0)))
            while (var.get('i')<=var.get('n')):
                var.put('coeff', var.get('i'), '*')
                # update
                (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
            #for JS loop
            var.put('i', Js(1.0))
            while (var.get('i')<=var.get('k')):
                var.put('coeff', var.get('i'), '/')
                # update
                (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
            return var.get('coeff')
        PyJsHoisted_binom_.func_name = 'binom'
        var.put('binom', PyJsHoisted_binom_)
        @Js
        def PyJsHoisted_bezCoeff_(i, func, this, arguments, var=var):
            var = Scope({'i':i, 'func':func, 'this':this, 'arguments':arguments}, var)
            var.registers(['j', 'i', 'bc', 'polyCoeffs', 'func'])
            var.put('polyCoeffs', var.get('chebyPolyCoeffs')(var.get('p'), var.get('func')))
            #for JS loop
            PyJsComma(var.put('bc', Js(0.0)),var.put('j', Js(0.0)))
            while (var.get('j')<=var.get('i')):
                var.put('bc', ((var.get('binom')(var.get('i'), var.get('j'))*var.get('polyCoeffs').get(var.get('j')))/var.get('binom')(var.get('p'), var.get('j'))), '+')
                # update
                (var.put('j',Js(var.get('j').to_number())+Js(1))-Js(1))
            return var.get('bc')
        PyJsHoisted_bezCoeff_.func_name = 'bezCoeff'
        var.put('bezCoeff', PyJsHoisted_bezCoeff_)
        var.put('PI', var.get('Math').get('PI'))
        var.put('Rpitch', ((var.get('module')*var.get('numTeeth'))/Js(2.0)))
        var.put('phi', (var.get('pressureAngle') or Js(20.0)))
        var.put('Rb', (var.get('Rpitch')*var.get('Math').callprop('cos', ((var.get('phi')*var.get('PI'))/Js(180.0)))))
        var.put('Ra', (var.get('Rpitch')+var.get('module')))
        var.put('p', (var.get('order') or Js(3.0)))
        var.put('ta', (var.get('Math').callprop('sqrt', ((var.get('Ra')*var.get('Ra'))-(var.get('Rb')*var.get('Rb'))))/var.get('Rb')))
        var.put('stop', (var.get('fstop') or Js(1.0)))
        var.put('start', Js(0.01))
        var.put('bzCoeffs', Js([]))
        pass
        pass
        pass
        pass
        pass
        pass
        if (PyJsStrictNeq(var.get('fstart'),var.get('undefined')) and (var.get('fstart')<var.get('stop'))):
            var.put('start', var.get('fstart'))
        var.put('te', (var.get('Math').callprop('sqrt', var.get('stop'))*var.get('ta')))
        var.put('ts', (var.get('Math').callprop('sqrt', var.get('start'))*var.get('ta')))
        #for JS loop
        var.put('i', Js(0.0))
        while (var.get('i')<=var.get('p')):
            var.put('bcoeff', Js({}))
            var.get('bcoeff').put('x', var.get('bezCoeff')(var.get('i'), var.get('involuteXbez')))
            var.get('bcoeff').put('y', var.get('bezCoeff')(var.get('i'), var.get('involuteYbez')))
            var.get('bzCoeffs').callprop('push', var.get('bcoeff'))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        return var.get('bzCoeffs')
    PyJs_involuteBezCoeffs_1_._set_name('involuteBezCoeffs')
    var.put('involuteBezCoeffs', PyJs_involuteBezCoeffs_1_)
    pass
    pass
    pass
    pass
    @Js
    def PyJs_createGearTooth_2_(module, teeth, pressureAngle, rotRads, this, arguments, var=var):
        var = Scope({'module':module, 'teeth':teeth, 'pressureAngle':pressureAngle, 'rotRads':rotRads, 'this':this, 'arguments':arguments, 'createGearTooth':PyJs_createGearTooth_2_}, var)
        var.registers(['outData', 'module', 'rotRads', 'pt', 'i', 'Z', 'phi', 'rot', 'pressureAngle', 'm', 'teeth', 'inData'])
        var.put('m', var.get('module'))
        var.put('Z', var.get('teeth'))
        var.put('phi', (var.get('pressureAngle') or Js(20.0)))
        var.put('rot', (var.get('rotRads') or Js(0.0)))
        var.put('inData', var.get('genGearToothData')(var.get('m'), var.get('Z'), var.get('phi')))
        var.put('outData', Js([]))
        #for JS loop
        var.put('i', Js(0.0))
        while (var.get('i')<var.get('inData').get('length')):
            if PyJsStrictNeq(var.get('inData').get(var.get('i')).get('x'),var.get('undefined')):
                var.put('pt', var.get('rotate')(var.get('inData').get(var.get('i')), var.get('rot')))
                var.get('outData').callprop('push', var.get('pt').get('x'), var.get('pt').get('y'))
            else:
                var.get('outData').callprop('push', var.get('inData').get(var.get('i')))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        return var.get('outData')
    PyJs_createGearTooth_2_._set_name('createGearTooth')
    var.put('createGearTooth', PyJs_createGearTooth_2_)
    pass
    @Js
    def PyJs_createIntGearTooth_3_(module, teeth, pressureAngle, rotRads, this, arguments, var=var):
        var = Scope({'module':module, 'teeth':teeth, 'pressureAngle':pressureAngle, 'rotRads':rotRads, 'this':this, 'arguments':arguments, 'createIntGearTooth':PyJs_createIntGearTooth_3_}, var)
        var.registers(['outData', 'module', 'rotRads', 'pt', 'i', 'Z', 'phi', 'rot', 'pressureAngle', 'm', 'teeth', 'inData'])
        var.put('m', var.get('module'))
        var.put('Z', var.get('teeth'))
        var.put('phi', (var.get('pressureAngle') or Js(20.0)))
        var.put('rot', (var.get('rotRads') or Js(0.0)))
        var.put('inData', var.get('genIntGearToothData')(var.get('m'), var.get('Z'), var.get('phi')))
        var.put('outData', Js([]))
        #for JS loop
        var.put('i', Js(0.0))
        while (var.get('i')<var.get('inData').get('length')):
            if PyJsStrictNeq(var.get('inData').get(var.get('i')).get('x'),var.get('undefined')):
                var.put('pt', var.get('rotate')(var.get('inData').get(var.get('i')), var.get('rot')))
                var.get('outData').callprop('push', var.get('pt').get('x'), var.get('pt').get('y'))
            else:
                var.get('outData').callprop('push', var.get('indata').get(var.get('i')))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        return var.get('outData')
    PyJs_createIntGearTooth_3_._set_name('createIntGearTooth')
    var.put('createIntGearTooth', PyJs_createIntGearTooth_3_)
    pass
    @Js
    def PyJs_createGearOutline_4_(module, teeth, pressureAngle, shaftRadius, this, arguments, var=var):
        var = Scope({'module':module, 'teeth':teeth, 'pressureAngle':pressureAngle, 'shaftRadius':shaftRadius, 'this':this, 'arguments':arguments, 'createGearOutline':PyJs_createGearOutline_4_}, var)
        var.registers(['toothData', 'shaftRadius', 'module', 'r', 'rotToothData', '_gearData', 'i', 'gearData', 'Z', 'phi', 'pressureAngle', 'm', 'teeth'])
        var.put('m', var.get('module'))
        var.put('Z', var.get('teeth'))
        var.put('phi', (var.get('pressureAngle') or Js(20.0)))
        var.put('toothData', var.get('genGearToothData')(var.get('m'), var.get('Z'), var.get('phi')))
        var.put('rotToothData', var.get('rotateTooth')(var.get('toothData')))
        var.put('gearData', Js([]).callprop('concat', var.get('rotToothData')))
        #for JS loop
        var.put('i', Js(1.0))
        while (var.get('i')<var.get('Z')):
            pass
            var.put('rotToothData', var.get('rotateTooth')(var.get('toothData'), (((Js(2.0)*var.get('Math').get('PI'))*var.get('i'))/var.get('teeth'))))
            var.put('_gearData', var.get('gearData')).get('push').callprop('apply', var.get('_gearData'), var.get('_toConsumableArray')(var.get('rotToothData').callprop('slice', Js(3.0))))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        var.get('gearData').callprop('push', Js('Z'))
        if (var.get('shaftRadius') and (var.get('shaftRadius')>Js(0.0))):
            var.put('r', var.get('shaftRadius'))
            var.get('gearData').callprop('push', Js('M'), (-var.get('r')), Js(0.0), Js('a'), var.get('r'), var.get('r'), Js(0.0), Js(1.0), Js(0.0), (var.get('r')*Js(2.0)), Js(0.0), Js('a'), var.get('r'), var.get('r'), Js(0.0), Js(1.0), Js(0.0), ((-var.get('r'))*Js(2.0)), Js(0.0), Js('z'))
        return var.get('gearData')
    PyJs_createGearOutline_4_._set_name('createGearOutline')
    var.put('createGearOutline', PyJs_createGearOutline_4_)
    @Js
    def PyJs_createIntGearOutline_5_(module, teeth, pressureAngle, rimRadius, this, arguments, var=var):
        var = Scope({'module':module, 'teeth':teeth, 'pressureAngle':pressureAngle, 'rimRadius':rimRadius, 'this':this, 'arguments':arguments, 'createIntGearOutline':PyJs_createIntGearOutline_5_}, var)
        var.registers(['toothData', '_gearData2', 'module', 'r', 'rotToothData', 'rimRadius', 'i', 'gearData', 'Z', 'phi', 'pressureAngle', 'm', 'teeth'])
        var.put('m', var.get('module'))
        var.put('Z', var.get('teeth'))
        var.put('phi', (var.get('pressureAngle') or Js(20.0)))
        var.put('toothData', var.get('genIntGearToothData')(var.get('m'), var.get('Z'), var.get('phi')))
        var.put('rotToothData', var.get('rotateTooth')(var.get('toothData')))
        var.put('gearData', Js([]).callprop('concat', var.get('rotToothData')))
        #for JS loop
        var.put('i', Js(1.0))
        while (var.get('i')<var.get('Z')):
            pass
            var.put('rotToothData', var.get('rotateTooth')(var.get('toothData'), (((Js(2.0)*var.get('Math').get('PI'))*var.get('i'))/var.get('teeth'))))
            var.put('_gearData2', var.get('gearData')).get('push').callprop('apply', var.get('_gearData2'), var.get('_toConsumableArray')(var.get('rotToothData').callprop('slice', Js(3.0))))
            # update
            (var.put('i',Js(var.get('i').to_number())+Js(1))-Js(1))
        var.get('gearData').callprop('push', Js('Z'))
        if (var.get('rimRadius') and (var.get('rimRadius')>Js(0.0))):
            var.put('r', var.get('rimRadius'))
            var.get('gearData').callprop('push', Js('M'), (-var.get('r')), Js(0.0), Js('a'), var.get('r'), var.get('r'), Js(0.0), Js(1.0), Js(0.0), (var.get('r')*Js(2.0)), Js(0.0), Js('a'), var.get('r'), var.get('r'), Js(0.0), Js(1.0), Js(0.0), ((-var.get('r'))*Js(2.0)), Js(0.0), Js('z'))
        return var.get('gearData')
    PyJs_createIntGearOutline_5_._set_name('createIntGearOutline')
    var.put('createIntGearOutline', PyJs_createIntGearOutline_5_)
PyJs_anonymous_0_._set_name('anonymous')
PyJs_anonymous_0_()
pass
