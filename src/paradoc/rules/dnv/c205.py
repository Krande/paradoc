import logging

import numpy as np

from paradoc.utils import closest_val_in_dict

from ..config import Settings as _Settings


class ShapeFactor:
    @staticmethod
    def box(breadth, depth, height):
        box_factors = {
            4: {0: 1.2, 1: 1.3, 2: 1.4, 4: 1.5, 6: 1.6},
            3: {0: 1.1, 1: 1.2, 2: 1.25, 4: 1.35, 6: 1.4},
            2: {0: 1.0, 1: 1.05, 2: 1.1, 4: 1.15, 6: 1.2},
            1.5: {0: 0.95, 1: 1.0, 2: 1.05, 4: 1.1, 6: 1.15},
            1: {0: 0.9, 1: 0.95, 2: 1.05, 4: 1.05, 6: 1.1, 10: 1.2},
            2 / 3: {0: 0.8, 1: 0.85, 2: 0.9, 4: 0.95, 6: 1.0},
            1 / 2: {0: 0.75, 1: 0.75, 2: 0.8, 4: 0.85, 6: 0.9},
            1 / 3: {0: 0.7, 1: 0.75, 2: 0.75, 4: 0.75, 6: 0.8},
            1 / 4: {0: 0.7, 1: 0.7, 2: 0.75, 4: 0.75, 6: 0.75},
        }
        lw = closest_val_in_dict(breadth / depth, box_factors)
        h_b = height / breadth
        hb = 0 if h_b <= 1 else closest_val_in_dict(h_b, box_factors[lw])

        return box_factors[lw][hb]


class Wind:
    z_0 = 10
    n = 0.468
    t_0 = 3600

    def __init__(self, hour_mean_wind=36):
        """
        For moderate and strong wind speeds and neutral conditions. Frøya wind spectrum

        Annual probability of exceedance of 36 m/s: 1e-2
        Annual probability of exceedance of 41 m/s: 1e-4
        :param hour_mean_wind:
        :param breadth: Dimension normal to wind direction
        :param depth: Dimension parallel to wind direction
        """
        self._hour_mean_wind = hour_mean_wind

    @property
    def hour_mean_wind(self):
        return self._hour_mean_wind

    @property
    def c(self):
        return 5.73e-2 * (1 + 0.15 * self.hour_mean_wind) ** 0.5

    def characteristic_velocity(self, z, time_period):
        """

        :param z:
        :param time_period: Average time
        :return:
        """
        return self.mean_wind(z) * (1 - 0.41 * self.turbulence(z) * np.log(time_period / Wind.t_0))

    def mean_wind(self, z):
        return self.hour_mean_wind * (1 + self.c * np.log(self.elevation(z)))

    def turbulence(self, z):
        return 0.06 * (1 + 0.043 * self.hour_mean_wind) * (self.elevation(z)) ** (-0.22)

    @staticmethod
    def elevation(z):
        """

        :param z: Height above sea level
        :return:
        """
        return z / Wind.z_0


class WindLoad(Wind):
    # DNVGL-RP-C205
    temp_0 = 15
    density = {0: 1.293, 5: 1.270, 10: 1.247, 15: 1.226, 20: 1.205, 25: 1.184, 30: 1.165}
    kin_visc = {0: 1.32e-5, 5: 1.36e-5, 10: 1.41e-5, 15: 1.45e-5, 20: 1.50e-5, 25: 1.55e-5, 30: 1.60e-5}

    def __init__(self, hour_mean_wind, shape_factor):
        super(WindLoad, self).__init__(hour_mean_wind)
        self._shape_factor = shape_factor

    @property
    def shape_factor(self):
        return self._shape_factor

    def pressure(self, z, time_period, temp=temp_0):
        return 0.5 * WindLoad.density[temp] * self.characteristic_velocity(z, time_period) ** 2

    def force(self, z, time_period, area, temp=temp_0):
        return self.pressure(z, time_period, temp) * self.shape_factor * area * np.sin(self.angle())

    def angle(self):
        return np.pi / 2

    @staticmethod
    def reynold(speed, width, temp=temp_0):
        return speed * width / WindLoad.kin_visc[temp]


class WindSpectrum(Wind):
    @staticmethod
    def area(freq, p1, p2):
        def alpha(i):
            return [2.9, 45.0, 13.0][i]

        def q(i):
            return 1.0 if i < 2 else 1.25

        def p(i):
            return 0.4 if i < 2 else 0.5

        def r(i):
            return 0.92 if i < 2 else 0.85

        def delta(coord1, coord2):
            return np.abs(coord1 - coord2)

        def z_g():
            return np.sqrt(p1.z * p2.z) / Wind.z_0

        return np.sqrt(
            np.sum(
                np.array(
                    [
                        alpha(i) * freq ** r(i) * delta(c1, c2) ** q(i) * z_g() ** (-p(i))
                        for i, (c1, c2) in enumerate(zip(p1.p, p2.p))
                    ]
                )
            )
        )

    def froya_density(self, freq, z):
        return 320 * (
            ((self.hour_mean_wind / 10) ** 2 * self.elevation(z) ** 0.45)
            / (1 + self.spectrum_freq(freq, z) ** self.n) ** (5 / (3 * Wind.n))
        )

    def spectrum_freq(self, freq, z):
        return 172 * freq * self.elevation(z) ** (2 / 3) * (self.hour_mean_wind / 10) ** (-0.75)

    def harris_density(self, freq):
        return

    def spectral_moment(self, j, s_density, *args):
        from scipy.integrate import quad

        res, err = quad(lambda x: x ** j * s_density(x, *args), 0, np.inf)
        if err > _Settings.point_tol:
            logging.info(f"Spectral moment as an error of {err}. Integral result: {res}")
        return res

    def spectral_variance(self, spectral_density):
        return np.sqrt(self.spectral_moment(0, spectral_density))

    def coherence_spectrum(self, freq, p1, p2):
        """
        p1.x and p2.x is along-wind position
        p1.y and p2.y is across-wind position
        p1.z and p2.z is elevations

        :param freq:
        :param p1:
        :param p2:
        :return:
        """

        return np.exp(-np.sqrt(self.area(freq, p1, p2)))
