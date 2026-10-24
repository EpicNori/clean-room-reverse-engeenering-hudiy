"""Session-only estimates; gaps/disconnects invalidate runs and fuel integration."""
import math


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


class DrivingStats:
    def __init__(self): self.reset()
    def reset(self):
        self.previous=None; self.armed=False; self.still_since=None; self.started=None
        self.last_run=None; self.best_run=None; self.distance=0.; self.fuel=0.
    def update(self,stamp,values,custom,settings):
        speed=values.get('speed')
        result={'acceleration':None,'zeroToHundred':self.last_run,'range':None,'averageConsumption':None,'bestZeroToHundred':self.best_run}
        if not finite(stamp) or not finite(speed) or not 0<=speed<=350:
            self.previous=None; self.armed=False; self.started=None; self.still_since=None
            self.distance=self.fuel=0.
            return result
        previous=self.previous; dt=stamp-previous[0] if previous else 0
        if previous and not 0<dt<=3:
            self.previous=None; self.armed=False; self.started=None; self.still_since=None
            self.distance=self.fuel=0.; previous=None
        if previous:
            acceleration=(speed-previous[1])/3.6/dt
            if abs(acceleration)>30:
                self.previous=(stamp,speed);self.armed=False;self.started=None;self.still_since=None;self.distance=self.fuel=0.
                return result
            result['acceleration']=round(acceleration,3)
            if self.armed and self.started is None and speed>1.5: self.started=previous[0]; self.armed=False
            if self.started is not None:
                if speed>=100 and previous[1]<100 and speed>previous[1]:
                    crossing=previous[0]+dt*(100-previous[1])/(speed-previous[1])
                    self.last_run=round(crossing-self.started,2)
                    if self.last_run>0: self.best_run=min(self.best_run,self.last_run) if self.best_run else self.last_run
                    self.started=None
                elif stamp-self.started>120 or speed<=1: self.started=None
        if speed<=1:
            if self.still_since is None: self.still_since=stamp
            if stamp-self.still_since>=2: self.armed=True
        else: self.still_since=None
        def source(name):
            key=settings.get(name)
            if not key: return None
            kind,_,identifier=key.partition(':')
            if kind=='builtin': return values.get(identifier)
            sample=custom.get(identifier,{})
            if sample.get('error') or not finite(sample.get('timestamp')) or not 0<=stamp-sample['timestamp']<=10: return None
            return sample.get('value')
        rate,level=source('fuelRate'),source('fuelLevel')
        valid_rate=finite(rate) and 0<=rate<=250
        if not valid_rate:self.distance=self.fuel=0.
        if previous and speed>=5 and valid_rate:
            self.distance+=(speed+previous[1])/2*dt/3600
            self.fuel+=rate*dt/3600
        if self.distance>=.1 and self.fuel>0:
            consumption=self.fuel/self.distance*100
            result['averageConsumption']=round(consumption,2)
            tank=settings.get('tankLitres')
            if finite(tank) and finite(level) and 0<=level<=100 and valid_rate:
                result['range']=round(tank*level/100/consumption*100,1)
        self.previous=(stamp,speed)
        result.update(zeroToHundred=self.last_run,bestZeroToHundred=self.best_run)
        return result
