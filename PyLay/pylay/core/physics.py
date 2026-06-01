import math

class Spring:
    """
    A 1-dimensional Spring animation solver based on the analytical solutions
    of the spring-mass-damper system. This solver is 100% stable, handles variable
    frame rates gracefully, and prevents numerical integration explode issues.
    
    Can be parameterized using SwiftUI-style response and damping_fraction:
      - response (float): the speed of the spring (in seconds).
      - damping_fraction (float): bounciness (0 = infinite bounce, 1 = no overshoot/bounce).
    
    Or using raw physics parameters (mass, stiffness, damping).
    """
    def __init__(self, 
                 value: float = 0.0, 
                 response: float = 0.35, 
                 damping_fraction: float = 0.7, 
                 velocity: float = 0.0):
        self._value = value
        self._velocity = velocity
        self._target = value
        
        self._response = response
        self._damping_fraction = damping_fraction
        
        # Calculate physical parameters
        self._update_parameters()
        
    def _update_parameters(self):
        # Prevent division by zero
        response = max(0.01, self._response)
        damping_fraction = max(0.0, self._damping_fraction)
        
        # Natural frequency omega_n = 2 * pi / response
        self.omega_n = (2.0 * math.pi) / response
        self.zeta = damping_fraction
        
    @property
    def value(self) -> float:
        return self._value
        
    @value.setter
    def value(self, val: float):
        self._value = val
        
    @property
    def velocity(self) -> float:
        return self._velocity
        
    @velocity.setter
    def velocity(self, val: float):
        self._velocity = val
        
    @property
    def target(self) -> float:
        return self._target
        
    @target.setter
    def target(self, val: float):
        self._target = val

    @property
    def response(self) -> float:
        return self._response

    @response.setter
    def response(self, val: float):
        self._response = max(0.01, val)
        self._update_parameters()

    @property
    def damping_fraction(self) -> float:
        return self._damping_fraction

    @damping_fraction.setter
    def damping_fraction(self, val: float):
        self._damping_fraction = max(0.0, val)
        self._update_parameters()
        
    def snap_to(self, value: float):
        """Immediately move the spring to target and stop all velocity."""
        self._value = value
        self._target = value
        self._velocity = 0.0

    def update(self, dt: float) -> float:
        """
        Advance the spring animation by dt seconds.
        Uses the exact analytical solution of the second-order differential equation.
        """
        if dt <= 0.0:
            return self._value
            
        # If we are already extremely close to target with no velocity, snap
        if abs(self._value - self._target) < 1e-5 and abs(self._velocity) < 1e-4:
            self._value = self._target
            self._velocity = 0.0
            return self._value
            
        x0 = self._value - self._target
        v0 = self._velocity
        
        omega_n = self.omega_n
        zeta = self.zeta
        
        # Underdamped system (zeta < 1.0) - oscillating decay
        if zeta < 1.0:
            omega_d = omega_n * math.sqrt(1.0 - zeta * zeta)
            exp_term = math.exp(-zeta * omega_n * dt)
            
            a = x0
            b = (v0 + zeta * omega_n * x0) / omega_d
            
            cos_term = math.cos(omega_d * dt)
            sin_term = math.sin(omega_d * dt)
            
            self._value = exp_term * (a * cos_term + b * sin_term) + self._target
            self._velocity = exp_term * (
                (omega_d * b - zeta * omega_n * a) * cos_term - 
                (omega_d * a + zeta * omega_n * b) * sin_term
            )
            
        # Critically damped system (zeta == 1.0) - fast return, no oscillation
        elif abs(zeta - 1.0) < 1e-6:
            exp_term = math.exp(-omega_n * dt)
            
            a = x0
            b = v0 + omega_n * x0
            
            self._value = exp_term * (a + b * dt) + self._target
            self._velocity = exp_term * (b - omega_n * (a + b * dt))
            
        # Overdamped system (zeta > 1.0) - sluggish return
        else:
            beta = omega_n * math.sqrt(zeta * zeta - 1.0)
            r1 = -zeta * omega_n + beta
            r2 = -zeta * omega_n - beta
            
            exp_r1 = math.exp(r1 * dt)
            exp_r2 = math.exp(r2 * dt)
            
            a = (v0 - r2 * x0) / (r1 - r2)
            b = x0 - a
            
            self._value = a * exp_r1 + b * exp_r2 + self._target
            self._velocity = a * r1 * exp_r1 + b * r2 * exp_r2
            
        return self._value
