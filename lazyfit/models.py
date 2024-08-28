import numpy as np
import math as m
import lazyfit.utility as utility
import types

import scipy.special
import scipy.signal
import inspect
#import matplotlib.pyplot as plt

pi = np.pi
inf = float('inf')

###########################################
#### create class for fit models
###########################################

class LazyFitModel:
	'''Class for containg fitmodels. '''

	def __init__(self, name, f, guess=None, bounds=None, math_string=None, description=None ):
		self.name = name # string containing model name
		self.f = f # function for evaluating model
		self.string = math_string # string with math expression
		self.guess = guess # function for getting guess
		self.bounds = bounds # function for getting bounds
		self.description = description # additional description

	def get_param_names(self):
		'''return dictionary with names of fit parameters'''
		return inspect.getfullargspec(self.f).args[1::]  # get fit function arguments but without 'x' which is always first argument

	def __repr__(self):
		'''show some usefull information when printing the model object in the terminal'''
		return f'<LazyFitModel "{self.name}". Fit parameters: {self.get_param_names()}>'

###########################################
# generic functions
###########################################

def peak_finder(x, y):
	'''generic function for finding the biggest peak in (x,y) data.
	Returns a tupple of peak amplitude, position, FWHM and background'''

	B = np.min(y)  # background estimate
	A = np.max(y) - B  # peak amplitude
	x0 = x[np.argmax(y)]  # position estimate

	# the hard part, estimating the FWHM.
	# this we do by finding the value where the y drops by 0.5
	# note, we assume that x is in increasing order!
	filter_under_half = (y - B) < A / 2  # filter where background corrected signal is below 50% of peak
	try:
		a = x[np.max(
			np.argwhere(filter_under_half * (x < x0)))]  # x value of the first point to the left of the peak going below
		b = x[np.min(
			np.argwhere(filter_under_half * (x > x0)))]  # x value of the first point to the right of the peak going below
		FWHM = np.abs(b - a)  # full width half maximum
	except ValueError: # catch the case where argwhere works on an empty array
		FWHM = 0

	return [A, x0, FWHM, B]


def find_2peaks(x, y):
	'''roughly estimates the properties of the two most prominent peaks in the (x,y) data
	Returns a tupple with [A1, x1, FWHM1, A2, x2, FWHM2, B]
	A1 is amplitude of first peak
	x1 is position of first peak
	FWHM is full width half maximum of first peak
	Next 3 parameters are the same but for the second peak
	B is a constant background
	'''

	# first detect the largest peak
	A1, x1, FWHM1, B1 = peak_finder(x,y)

	# subtract a gaussian resembling the first peak
	y2 = y - _func_gaussian(x, A1, x1, FWHM1/2.35, 0)
	y2 = np.maximum(y2, B1) # prevent the new data from going below the previous minimum

	# debugging
	#plt.figure()
	#plt.plot(x, y, label='data')
	#plt.plot(x, _func_gaussian(x, A1, x1, FWHM1/2.35, 0), label='gauss')
	#plt.plot(x, y2, label='data-gauss')
	#plt.legend()

	# find the second peak
	A2, x2, FWHM2, B2 = peak_finder(x, y2)
	if FWHM2 == 0: # this sometimes happens if we cant find a FWHM
		FWHM2 = FWHM1
	return  [A1, x1, FWHM1, A2, x2, FWHM2, B1]

###########################################
# lorentzian peak
###########################################
def _func_lorentz(x, A, x0, FWHM, B):
	"""Lorentzian peak plus constant backgrond.
	A/(1+(x-x0)**2/(FWHM/2)**2) + B

	Parameters:
	x		xdata
	A 		peak amplitude
	x0 		peak location
	FWHM	full widht half maximum
	B		constant background
	"""
	return A/(1+(x-x0)**2/(FWHM/2)**2) + B

def _guess_lorentz(x, y):
	return peak_finder(x,y)

def _bounds_lorentz(x, y):
	# assume peak to be withing x data, define FWHM to be positive
	lb = [-inf, np.min(x), 0, -inf]
	ub = [inf, np.max(x), inf, inf]
	return (lb, ub)

lorentz = LazyFitModel('lorentz', _func_lorentz, _guess_lorentz, _bounds_lorentz, 'A/(1+(x-x0)^2/(FWHM/2)^2)+B')

###########################################
# exponential decay
###########################################

def _func_exp(x, A, Gamma, B):
	"""Single exponential decay plus constant background
	A*np.exp(-x*Gamma) + B

	Parameters:
	x		xdata
	A		amplitude
	Gamma	decay rate
	B		constant background
	"""
	return A*np.exp(-x*Gamma) + B

def _guess_exp(x,y):
	B = np.min(y)
	A = np.max(y)-B

	# find where y data falls to 1/e. This must occour after the maximum. Thus, we only consider the post-max data.
	try:
		filt = x>x[np.argmax(y)]
		x1 = x[filt]
		y1 = y[filt]
		e_time = x1[np.min(np.argwhere(y1-B<A*np.exp(-1)))]
		Gamma = 1/e_time
	except Exception:
		Gamma = 0

	return [A, Gamma, B]

def _bounds_exp(x,y):
	lb = [0,0,-inf]
	ub = [inf, inf, inf]
	return lb,ub

exp = LazyFitModel('exp', _func_exp, _guess_exp, _bounds_exp, 'A*exp(-x*Gamma) + B')

###########################################
# biexponential decay
###########################################

def _func_biexp(x, A1, Gamma1, A2, Gamma2, B):
	"""Biexponential decay plus constant background
	A1*np.exp(-x*Gamma1) + A2*np.exp(-x*Gamma2) + B

	Params:
	x		xdata
	A1		amplitude of first exponential
	Gamma1	decay rate of first exponential
	A2		amplitude of second exponential
	Gamma2	decay rate of second exponential
	B 		constant background
	"""
	return A1*np.exp(-x*Gamma1) + A2*np.exp(-x*Gamma2) + B

def _guess_biexp(x,y):
	A, Gamma, B = _guess_exp(x,y) # use the monoexponential guess, assume the second exponential is zero
	return [A, Gamma, 0, 0, B]

def _bounds_biexp(x,y):
	lb = [0, 0, 0, 0, -inf]
	ub = [inf, inf, inf, inf, inf]
	return lb,ub

biexp = LazyFitModel('biexp', _func_biexp, _guess_biexp, _bounds_biexp, 'A1*exp(-x*Gamma1)+A2*exp(-x*Gamma2) + B')

###########################################
# exponential decay convolved  with gaussian response
###########################################

def _func_convexp(x, A, Gamma, B,  x0, s):
	"""Single exponential decay convolved with Gaussian response plus background

	Parameters:
	x 		xdata
	A 		exponential amplitude post convolution
	Gamma	exponential decay rate
	B		constant background
	x0		start time of exponential decay
	s		standard deviation of detector response
		"""

	if s == 0:
		return (x>=x0) * A * np.exp(-Gamma*(x-x0)) + B

	peakval = np.exp(0.5*Gamma**2*s**2)*scipy.special.erfc(Gamma*s/np.sqrt(2))
	return (A/peakval)*np.exp(-Gamma*(x-x0)+0.5*Gamma**2*s**2)*scipy.special.erfc((-(x-x0)/s+Gamma*s)/np.sqrt(2)) + B

def _guess_convexp(x, y):
	x0 = x[np.argmax(y)]
	A = np.max(y)
	B = np.min(y)

	# find 1/e time. This must occour after the maximum. For this reason, we define a new set of xvalues. This is need incase the
	try:
		filt = x > x0
		x1 = x[filt]
		y1 = y[filt]
		e_time = x1[np.min(np.argwhere(y1 - B < A * np.exp(-1)))]
		Gamma = 1 / e_time
	except Exception:
		Gamma = 0

	# assume that the instrument response correspondsto 10% of the decay time
	s = 0.1/Gamma

	return [A, Gamma, B, x0, s]

def _bounds_convexp(x,y):
	lb = [0, 0, -inf, -inf, 0]
	ub = [inf, inf, inf, inf, inf]
	return lb,ub

convexp = LazyFitModel('conexp', _func_convexp, _guess_convexp, _bounds_convexp, 'A*exp(-x*Gamma) conv N(x;0,s) + B')


###########################################
# T1
###########################################

def _func_T1(x, A, T1, B):
	"""Single exponential decay plus constant background
	A*(1-np.exp(-x/T1)) + B

	Parameters:
	x		xdata
	A		amplitude
	T1		T1 correlation time
	B		constant background
	"""
	return A*(1-np.exp(-x/T1)) + B

def _guess_T1(x,y):

	[_, Gamma, _] = _guess_exp(x,-y)

	return [np.max(y), 1/Gamma, np.min(y)] # TODO, can be more accurate

def _bounds_T1(x,y):
	lb = [-inf,0,-inf]
	ub = [inf, inf, inf]
	return lb,ub

T1 = LazyFitModel('T1', _func_T1, _guess_T1, _bounds_T1, 'A*(1-exp(-x/T1)) + B')

###########################################
# Sinussoidal
###########################################

# Important note on fitting sines:
# Obviously, the phase is very important to get right. 
# Mathematically, we would like to restrict this to either 0..2pi or -pi..pi.
# Howevers, this can give numerical problems. Eg. The ideal phase might be 0.95pi, but the guess estimates -0.95 pi.
# If we enforce a -pi..pi bound, the fit might fail to move from -0.95pi to 0.95 despite the guess being physically close.
# My solution is to use a more generous -2pi to 2pi bounds on the phase, and restrict the guess to within -pi to pi. 
# This should guarantee convergence.

def _func_sine(x, A, f, phi, B):
	"""Sinussoid plus constant background
	A*np.sin(x*f*2*pi+phi)+B

	Parameters:
	x		xdata
	A		amplitude
	f		real frequency
	phi 	phase in 0 to 2 pi interval
	B		constant background
	"""
	return A*np.sin(x*f*2*pi+phi)+B

def _guess_sine(x,y):
	B = np.mean(y)
	A = np.sqrt(2)*np.std(y)
	f, _ = utility.get_main_fourier_component(x,y)

	# a robust phi estimate can be constructed by trying 8 different values, and calculating the inner product with the data
	phi_list = np.arange(-pi, pi, pi / 4) # see note above on limits on phi
	overlap = np.zeros(8)
	for i, phi in enumerate(phi_list):
		overlap[i] = np.sum((y - B) * _func_sine(x, 1, f, phi, 0))
	phi = phi_list[np.argmax(overlap)]
	return [A, f, phi, B]

def _bounds_sine(x, y):
	lb = [0,0, -2*pi,-inf] # see note above on limits on phi
	up = [inf, inf, 2*pi, inf]
	return (lb,up)

sine = LazyFitModel('sine', _func_sine, _guess_sine, _bounds_sine, 'A*sin(x*f*2pi+phi)+B')

###########################################
# Ramsey
###########################################

def _func_ramsey(x, A, f, phi, B, T2s, alpha):
	"""Decaying ramsey oscillations
	A*np.sin(x*f*2*pi+phi)*np.exp(-(x/T2s)**alpha)+B

	Parameters:
	x		xdata
	A 		amplitude for x=0
	f		real oscillation frequency
	phi		oscillation phase
	B		constant background
	T2s		1/e time of decay envelope (T2* time)
	alpha	exponential exponent of decay envelope
	"""
	return A*np.sin(x*f*2*pi+phi)*np.exp(-(x/T2s)**alpha)+B

def _guess_ramsey(x,y):
	return _guess_sine(x,y) + [np.max(x), 2] # Use guess for sine. Set T2* to x range, set alpha to 2

def _bounds_ramsey(x, y):
	lb = [0, 0, -2*pi, -inf, 0, 0]
	up = [inf, inf, 2*pi, inf, inf, inf]
	return (lb,up)

ramsey = LazyFitModel('ramsey', _func_ramsey, _guess_ramsey, _bounds_ramsey, 'A*sin(x*f*2pi+phi)*exp(-(x/T2s)^alpha)+B')

# for people who don't do Ramsey interferometry, we also include this model as "dampsine"

def _func_dampsine(x, A, f, phi, B, T, alpha):
	"""Exponentially decaying sine
	A*np.sin(x*f*2*pi+phi)*np.exp(-(x/T2s)**alpha)+B

	Parameters:
	x		xdata
	A 		amplitude for x=0
	f		real oscillation frequency
	phi		oscillation phase
	B		constant background
	T		1/e time of decay envelope
	alpha	exponential exponent of decay envelope
	"""
	return A*np.sin(x*f*2*pi+phi)*np.exp(-(x/T)**alpha)+B

dampsine = LazyFitModel('dampsine', _func_dampsine, _guess_ramsey, _bounds_ramsey, 'A*sin(x*f*2pi+phi)*exp(-(x/T)^alpha)+B')

###########################################
# Stretched exponential
###########################################

def _func_stretchexp(x, A, T, alpha):
	"""Stretched exponential
	A*np.exp(-(x/T)**alpha)

	Parameters:
	x		xdata
	A 		amplitude for x=0, this is initial visibility
	T		1/e time of decay envelope
	alpha	exponential exponent
	"""
	return A*np.exp(-(x/T)**alpha)

def _guess_stretchexp(x,y):

	# assume alpha = 1, use exponential guess
	A, gamma, B = _guess_exp(x,y)
	if gamma>0:
		T = 1/gamma
	else:
		T = np.mean(x)
	alpha = 1

	return [A, T, alpha]

def _bounds_stretchexp(x, y):
	lb = [0, 0, 0]
	up = [inf, inf, inf]
	return (lb,up)

stretchexp = LazyFitModel('stretchexp', _func_stretchexp, _guess_stretchexp, _bounds_stretchexp, 'A*exp(-(x/T)^alpha)')

# for compabability, we also include an alternative naming:

def _func_ramseyenvelope(x, A, T2s, alpha):
	"""
	Same function as stretchexp, but different naming convention.
	A*np.exp(-(x/T2)**alpha)

	Parameters:
	x		xdata
	A 		amplitude for x=0, this is initial visibility
	T		1/e time of decay envelope (T2 time)
	alpha	exponential exponent
	"""
	return A*np.exp(-(x/T2s)**alpha)

ramseyenvelope = LazyFitModel('ramseyenvelope', _func_ramseyenvelope, _guess_stretchexp, _bounds_stretchexp, 'A*exp(-(x/T2s)^alpha)')

###########################################
# two level saturation
###########################################

def _func_twolvlsat(x, Psat, Imax):
	"""Two level saturation.
	Imax/(1+Psat/x)

	Parameters:
	x 		xdata
	Psat	Saturation power, ie when intensity is half of max
	Imax	Intensity for x->inf
	"""

	with np.errstate(divide='ignore'): # ignore numpy divide by zero error
		return Imax/(1+Psat/x)

def _guess_twolvlsat(x,y):
	Imax = np.max(y)
	Psat = x[np.min(np.argwhere(y>Imax*0.5))] # take Psat as first point where y goes over 1/2 of max
	return [Psat, Imax]

def _bounds_twolvlsat(x, y):
	lb = [0, 0]
	ub = [inf, inf]
	return (lb,ub)

twolvlsat = LazyFitModel('twolvlsat', _func_twolvlsat, _guess_twolvlsat, _bounds_twolvlsat, 'Imax/(1+Psat/x)')

###########################################
# Rabi
###########################################

def _func_rabi(x, A, x_pi, B):
	"""Two-level Rabi oscillation
	A*np.sin((x/x_pi)*pi/2)**2+B

	Parameters:
	x		xdata
	A 		amplitude at a pi-pulse
	x_pi	pi-pulse power
	B		constant background
		"""
	return A*np.sin((x/x_pi)*pi/2)**2+B

def _guess_rabi(x,y):
	B = np.min(y)
	A = np.max(y)-B
	x_pi = 0.5 / utility.get_main_fourier_component(x, y)[0]
	return [A, x_pi, B]

def _bounds_rabi(x, y):
	lb = [0, 0, -inf]
	up = [inf, inf, inf]
	return (lb,up)

rabi = LazyFitModel('rabi', _func_rabi, _guess_rabi, _bounds_rabi, 'A*sin((x/x_pi)*pi/2)^2+B')

###########################################
# Unnormalised gaussian
###########################################

def _func_gaussian(x, A, x0, s, B):
	"""Gaussian peak plus constant bakground
	A * np.exp(-(x-x0)**2/(2*s**2)) + B

	Parameters:
	x		xdata
	A		peak amplitude
	x0		peak position
	s		Gaussian standard deviation
	B		constant background
	"""
	return A * np.exp(-(x-x0)**2/(2*s**2)) + B

def _guess_gaussian(x, y):
	A, x0, FWHM, B =  peak_finder(x, y)
	return [A, x0, FWHM/2.35, B]  # convert FWHM to standard deviation

def _bounds_gaussian(x, y):
	# assume peak to be withing x data, define sigma to be positive
	lb = [-inf, np.min(x), 0, -inf]
	ub = [inf, np.max(x), inf, inf]
	return lb, ub

gaussian = LazyFitModel('gaussian', _func_gaussian, _guess_gaussian, _bounds_gaussian, 'A*exp(-(x-x0)^2/(2*s^2)) + B')

###########################################
# Normalised gaussian
###########################################

def _func_normgaussian(x, A, x0, s):
	"""Normalised Gaussian
	A * np.exp(-(x-x0)**2/(2*s**2))/(np.sqrt(2*pi)*s)

	Parameters:
	x		xdadta
	A		area of Gaussian
	x0 		peak location
	s		Gaussian standard deviation
	"""
	return A * np.exp(-(x-x0)**2/(2*s**2))/(np.sqrt(2*pi)*s)

def _guess_normgaussian(x, y):
	A, x0, FWHM, B =  peak_finder(x, y)
	s = FWHM/2.35 # convert FWHM to standard deviation
	A *= np.sqrt(2*pi)*s
	return [A, x0, s]

def _bounds_normgaussian(x, y):
	# assume peak to be withing x data, define sigma to be positive
	lb = [0, np.min(x), 0]
	ub = [inf, np.max(x), inf]
	return lb, ub

normgaussian = LazyFitModel('normgaussian', _func_normgaussian, _guess_normgaussian, _bounds_normgaussian, 'A*Norm(x;x0,s)')

###########################################
# linear
###########################################

def _func_lin(x, A, B):
	"""Liner fit with y intercept
	A*x+B

	Parameters:
	x		xdata
	A		slope
	B		y-intercept
	"""
	return A * x + B

def _guess_lin(x, y):
	# this can be done analytically! See page 100 of Statistics by R. J. Barlow
	A = (np.mean(x*y)-np.mean(x)*np.mean(y))/(np.mean(x**2)-np.mean(x)**2)
	B = np.mean(y) - A*np.mean(x)
	return [A,B]

def _bounds_lin(x, y):
	# assume peak to be withing x data, define sigma to be positive
	lb = [-inf, -inf]
	ub = [inf, inf]
	return lb, ub

lin = LazyFitModel('lin', _func_lin, _guess_lin, _bounds_lin, 'A*x+B')

###########################################
# quadratic
###########################################

def _func_quadratic(x, A, B, C):
	"""Quadratic fit
	A*x^2 + B*x + C

	Parameters:
	x		xdata
	A		quadratic amplitude
	B		linear amplitude
	C		constant offset
	"""
	return A * x**2 + B*x + C

def _guess_quadratic(x, y):
	# again, this can be done analytically! But this is way uglier than the linear fit
	# see https://www.varsitytutors.com/hotmath/hotmath_help/topics/quadratic-regression

	x4 = np.sum(x**4)
	x3 = np.sum(x**3)
	x2 = np.sum(x**2)
	x1 = np.sum(x)

	x2y = np.sum(y*x**2)
	xy = np.sum(x*y)
	y = np.sum(y)
	n = len(x)

	guess = np.linalg.inv(np.array([[x4,x3,x2],[x3,x2,x1],[x2,x1,n]])) @ np.array([x2y,xy,y])
	return guess.tolist()

def _bounds_quadratic(x, y):
	# assume peak to be withing x data, define sigma to be positive
	lb = [-inf, -inf, -inf]
	ub = [inf, inf, inf]
	return lb, ub

quadratic = LazyFitModel('quadratic', _func_quadratic, _guess_quadratic, _bounds_quadratic, 'A*x^2+B*x+C')


###########################################
# Voigt
###########################################

def  _func_voigt(x, A, x0, L, G, B):
	'''Voigt lineshape (Lorentzian cnvolved with Gaussian) plus constant background

	Parameters:
	x		xdata
	A		peak amplitude
	x0		peak location
	L		Lorentzian FWHM
	G		Gaussian  FWHM
	B		constant background
	'''
	# note that the scipy function takes a gaussian standard deviation and a lorentzian half width half maximmum.
	# as we specify FWHM for both distributions we need to convert appropriately
	# we also divide with the function evaluated at zero detuning to ensure an amplitude of 1 at resonance
	return A*scipy.special.voigt_profile((x-x0), utility.FWHM_to_sigma(G), L/2)\
		   /scipy.special.voigt_profile(0, utility.FWHM_to_sigma(G), L/2) \
		   + B

def _guess_voigt(x,y):
	A, x0, FWHM, B = peak_finder(x, y) # do basic peak detection
	# we will assume that L=G, substite into the equation for effective Voigt linewidth (see utility.get_Voigt_FWHM() ) and solve for L
	L = FWHM/(0.5346+np.sqrt(1+0.2166))
	return [A, x0, L, L, B ]

def _bounds_voigt(x, y):
	lb = [-inf, np.min(x), 0, 0, -inf]
	ub = [inf, np.max(x), inf, inf, inf]
	return lb, ub

voigt = LazyFitModel('voigt', _func_voigt, _guess_voigt, _bounds_voigt, 'A*Voigt(x;x0,L,G)+B')

###########################################
# logistic
###########################################

def _func_logistic(x, A, B, x0, k,):
	"""Logistic rise plus constant background
	B + A/(1+np.exp(-(x-x0)*k))

	Parameters:
	x		xdata
	A		Amplitude of logistic, ie. f(inf)-f(-inf)
	B		constant background, ie. f(-inf)
	x0		50% location of logistic
	k		logistic rate
	"""
	return B + A/(1+np.exp(-(x-x0)*k))

def _guess_logistic(x, y):
	B = np.min(y)
	A = np.max(y) - np.min(y)
	x50 = x[np.argmin(np.abs(y-B-A/2))] # find where y is at 50%
	x10 = x[np.argmin(np.abs(y-B-A*0.1))] # 10% percentile
	x90 = x[np.argmin(np.abs(y - B - A * 0.9))]  # 90% percentile
	k = np.log(81)/(x90-x10) # convert 10-90% risetime to rate
	return [A,B, x50, k]

def _bounds_logistic(x, y):
	lb = [0, -inf, np.min(x), 0]
	ub = [inf, inf, np.max(x), inf]
	return (lb, ub)

logistic = LazyFitModel('logistic', _func_logistic, _guess_logistic, _bounds_logistic, 'A/(1+exp(-(x-x0)*k))+B')

###########################################
# logistic pulse
###########################################

def _func_logpulse(x, A, B, x0, x1, k0, k1):
	"""Logistic pulse. Product of rising and falling logistics.

	Parameters:
	x		xdata
	A		amplitude
	B		constant background
	x0		x value at 50% rise
	x1		x value at 50% fall
	k0		rise rate
	k1		fall rate
	"""
	return B + A*_func_logistic(x, 1, 0, x0, k0)*_func_logistic(x, 1, 0, x1, -k1) # second logpulse should be descending

def _guess_logpulse(x, y):
	B = np.min(y)
	A = np.max(y) - np.min(y)
	x0 = x[np.min(np.argwhere(y>B+A/2))] # find first x where y above half max
	x1 = x[np.max(np.argwhere(y>B+A/2))] # find last x where y above half max
	k = 5/(x1-x0)*10 # just assume for now that the risetime 10% of FWHM. This should be good enough for initial condition
	return [A, B, x0, x1, k, k]

def _bounds_logpulse(x, y):
	lb = [0, -inf, np.min(x), np.min(x), 0, 0]
	ub = [inf, inf, np.max(x), np.max(x), inf, inf]
	return (lb, ub)

logpulse = LazyFitModel('logpulse', _func_logpulse, _guess_logpulse, _bounds_logpulse, 'A/((1+exp(-(x-x0)k0))(1+exp(-(x+x0)k0)) + B')

###########################################
# Dual gaussian
###########################################

def _func_dualgaussian(x, A1, x1, s1, A2, x2, s2, B):
	"""Sum of two Gaussians and a constant background

	Parameters:
	x		xdata
	A1		amplitude of first Gaussian
	x1		position of first Gaussian
	s1		standard deviation of first Gaussian
	A2		amplitude of second Gaussian
	x2		position of second Gaussian
	s2		standard deviation of second Gaussian
	B		constant background
	"""
	return A1 * np.exp(-(x-x1)**2/(2*s1**2)) + A2 * np.exp(-(x-x2)**2/(2*s2**2)) + B

def _guess_dualgaussian(x, y):
	A1, x1, FWHM1, A2, x2, FWHM2, B = find_2peaks(x,y)
	return [A1, x1, FWHM1/2.35, A2, x2, FWHM2/2.35, B]  # convert FWHM to standard deviation

def _bounds_dualgaussian(x, y):
	# assume peak to be withing x data, define sigma to be positive
	lb = [-inf, np.min(x), 0, -inf, np.min(x), 0, -inf]
	ub = [inf, np.max(x), inf, inf, np.max(x), inf, inf]
	return lb, ub

dualgaussian = LazyFitModel('dualgaussian', _func_dualgaussian, _guess_dualgaussian, _bounds_dualgaussian, 'A1*Norm(x;x1,s1)+A2*Norm(x;x2,s2)+B')

###########################################
# Dual lorentz
###########################################

def _func_duallorentz(x, A1, x1, FWHM1, A2, x2, FWHM2, B):
	"""Sum of two Lorentzians and a constant background

	Parameters:
	x		xdata
	A1		amplitude of first Lorentzian
	x1		position of first Lorentzian
	FWHM1	full width half maximum of first Lorentzian
	A2		amplitude of second Lorentzian
	x2		position of second Lorentzian
	FWHM2	full width half maximum of first Lorentzian
	B		constant background
	"""
	return A1/(1+(x-x1)**2/(FWHM1/2)**2) + A2/(1+(x-x2)**2/(FWHM2/2)**2) + B

def _guess_duallorentz(x, y):
	A1, x1, FWHM1, A2, x2, FWHM2, B = find_2peaks(x,y)
	return [A1, x1, FWHM1, A2, x2, FWHM2, B]

def _bounds_duallorentz(x, y):
	# assume peak to be withing x data, define sigma to be positive
	lb = [-inf, np.min(x), 0, -inf, np.min(x), 0, -inf]
	ub = [inf, np.max(x), inf, inf, np.max(x), inf, inf]
	return lb, ub

duallorentz = LazyFitModel('duallorentz', _func_duallorentz, _guess_duallorentz, _bounds_duallorentz, 'A1*L(x;x1,FWHM1)+A2*L(x;x2,FWHM2)+B')
