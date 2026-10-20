"""
Class that contains plot templates for the live plot:

- Impedance-frequency plot
- Nyquist plot
- Bode plot
"""
#Imports
import matplotlib.pyplot as plt
import math

class PlotTemplates:
    """
    Plot templates for the live plot of the measurement results.

    The newest results are drawn in color, the results of the last
    (up to 5) complete measurement cycles are drawn in gray.

    All plot methods take the same arguments:

    - ``live_results`` (dict): Newest results with the keys ``id``, ``real``,
      ``imag`` and ``frequencies``.
    - ``current_results`` (list[dict]): All results of the current measurement cycle.
    - ``len_measurement_queue`` (int): Number of measurement setups per cycle.
    """

    def __init__(self):
        self.past_icm = 1 
        
        self.fig = None
        self.ax1 = None
        self.ax2 = None
        self.line_mag = None
        self.line_phase = None

        #live results
        self.real = []
        self.imag = []
        self.frequencies = []

        #past results
        self.past_results = []
        self.past_id = []
        self.past_real = []
        self.past_imag = []
        self.past_frequencies = []

        #plot impedance-frequency
        self.fig_imp = None
        self.ax_imp = None
        self.line_real = None
        self.line_imag = None
        self.line_past_real = None
        self.line_past_imag = None
        self._imp_shown = False

        #plot nyqhist
        # __init__
        self.fig_nyq = None
        self.ax_nyq = None
        self.line_nyq = None
        self.line_past_nyq = None
        self._nyq_shown = False


    def processing_results(self,test_current_id, live_results, current_results, len_measurement_queue):
        """
        Prepares the live results and the past results for plotting.

        When a measurement cycle is complete, it is added to the past results
        (only the last 5 cycles are kept).

        Args:
            live_results (dict): Newest results (keys ``id``, ``real``, ``imag``, ``frequencies``).
            current_results (list[dict]): All results of the current measurement cycle.
            len_measurement_queue (int): Number of measurement setups per cycle.
        """
        #process results liveplot
        """
        self.real = live_results["real"]
        self.imag = live_results["imag"]
        self.frequencies = live_results["frequencies"]
        """

        #check current id
        self.current_id = live_results["current_id"][0]
        icm = self.current_id.split(".")[0] 
        #icm = test_current_id.split(".")[0]

        if icm != self.past_icm:
            self.real = []
            self.imag = []
            self.frequencies = []
            self.past_icm = icm

        #test
        self.real.extend(live_results["real"])
        self.imag.extend(live_results["imag"])
        #self.frequencies.append(live_results["frequencies"]) test
        self.frequencies.append(live_results["frequencies"])

        #process past results
        if len(current_results) == len_measurement_queue:
            self.past_results.append(current_results)

            if len(self.past_results)>1: #if there are last results
                  
                if len(self.past_results)>5: #show only the last 5 results
                    del self.past_results[0]  

                #clear old results
                self.past_id = []
                self.past_real = []
                self.past_imag = []
                self.past_frequencies = []

                for sublist in self.past_results:
                # read every dict in the sublist and extend the corresponding lists
                    for item in sublist:

                        if 'id' in item:
                            self.past_id.extend(item['id'])
                        if 'real' in item:
                            self.past_real.extend(item['real'])
                        if 'imag' in item:
                            self.past_imag.extend(item['imag'])
                        if 'frequencies' in item:
                            self.past_frequencies.extend([item['frequencies']]) #test
    
    def _init_impedance_plot(self):
        """
        initializes the impedance-frequency plot with two lines: real and imaginary part of the impedance.
        The figure is created once; afterwards only the data of the lines is replaced.
        """
        with plt.ioff():   
            self.fig_imp, self.ax_imp = plt.subplots(figsize=(12, 6))
        self._imp_shown = False

        #past results
        self.line_past_real, = self.ax_imp.plot([], [], 'o', color='gray', alpha=0.3, markersize=4)
        self.line_past_imag, = self.ax_imp.plot([], [], 's', color='gray', alpha=0.3, markersize=4)
        self.line_past_mag, = self.ax_imp.plot([], [], 'd', color='gray', alpha=0.3, markersize=4)

        #live results
        self.line_real, = self.ax_imp.plot([], [], 'o-', color='r', label=r'$Z_{real}$')
        self.line_imag, = self.ax_imp.plot([], [], 's-', color='b', label=r'$Z_{imag}$')
        self.line_mag, = self.ax_imp.plot([], [], 'd-', color='g', label=r'$Z_{mag}$')

        # Set log scale for x-axis and labels
        self.ax_imp.set_xscale('log')
        self.ax_imp.set_xlabel('Frequency $f$ / Hz')
        self.ax_imp.set_ylabel(r'Impedance $Z$ / $\Omega$')
        self.ax_imp.set_title('Impedance as a Function of Frequency')
        self.ax_imp.grid(True, which='both', ls='--', alpha=0.3)
        self.ax_imp.tick_params(direction='in', which='both', top=True, right=True)

        #set legend
        self.fig_imp.legend(
            handles=[self.line_real, self.line_imag, self.line_mag],
            loc='center left', bbox_to_anchor=(0.8, 0.5),
            title='Legend', frameon=True,
        )
        self.fig_imp.subplots_adjust(right=0.78)


    def impedance_frequency(self, test_current_id, live_results, current_results, len_measurement_queue):
        """
        Plots the real and imaginary part of the impedance over the frequency (log scale).
        The figure is created once; afterwards only the data of the lines is replaced.

        Args:
            live_results (dict): Newest results (keys ``id``, ``real``, ``imag``, ``frequencies``).
            current_results (list[dict]): All results of the current measurement cycle.
            len_measurement_queue (int): Number of measurement setups per cycle.
        """
        # get processed data
        self.processing_results(test_current_id=test_current_id, live_results=live_results,
                                current_results=current_results,
                                len_measurement_queue=len_measurement_queue)

        # Only create the figure if it doesn't exist or has been closed
        if self.fig_imp is None or not plt.fignum_exists(self.fig_imp.number):
            self._init_impedance_plot()

        # live results
        self.line_real.set_data(self.frequencies, self.real)
        self.line_imag.set_data(self.frequencies, self.imag)
        #magnitude of impedance
        impedance = [math.hypot(r, i) for r, i in zip(self.real, self.imag)]
        self.line_mag.set_data(self.frequencies, impedance)

        # past results
        if self.past_real:
            self.line_past_real.set_data(self.past_frequencies, self.past_real)
            self.line_past_imag.set_data(self.past_frequencies, self.past_imag)
            past_impedance = [math.hypot(r, i) for r, i in zip(self.past_real, self.past_imag)]
            self.line_past_mag.set_data(self.past_frequencies, past_impedance)
        else:
            self.line_past_real.set_data([], [])
            self.line_past_imag.set_data([], [])
            self.line_past_mag.set_data([], [])

        #autoscale
        self.ax_imp.relim()
        self.ax_imp.autoscale_view()

        #
        self.fig_imp.canvas.draw()
        """        if not self._imp_shown:
            self.fig_imp.show()
            self._imp_shown = True"""

        self.fig_imp.canvas.flush_events()

    def _init_nyquist_plot(self):
        """
        initializes nyqhist plot 
        """
        with plt.ioff():   
            self.fig_nyq, self.ax_nyq = plt.subplots(figsize=(10, 7))
        self._nyq_shown = False

        #past results
        self.line_past_nyq, = self.ax_nyq.plot([], [], 'o', color='gray', alpha=0.3, markersize=4)

        #live results
        self.line_nyq, = self.ax_nyq.plot([], [], 'o-', color='b',
                                        label=r'$Z_{imag}$ vs $Z_{real}$')

        #plot format
        self.ax_nyq.set_xlabel(r'Real part $Z_{real}$ / $\Omega$')
        self.ax_nyq.set_ylabel(r'Imaginary part $Z_{imag}$ / $\Omega$')
        self.ax_nyq.set_title('Nyquist Plot')
        self.ax_nyq.axhline(0, color='black', linewidth=0.8, linestyle='-')
        self.ax_nyq.axvline(0, color='black', linewidth=0.8, linestyle='-')
        #Important for Nyquist-Plot: keep equal ratio of Y- and X-Axis
        self.ax_nyq.set_aspect('equal', adjustable='box')
        self.ax_nyq.grid(True, which='both', ls='--', alpha=0.3)
        self.ax_nyq.tick_params(direction='in', which='both', top=True, right=True)

        # Legend
        self.fig_nyq.legend(
            handles=[self.line_nyq],
            loc='center left', bbox_to_anchor=(0.8, 0.5),
            title='Legend', frameon=True,
        )
        self.fig_nyq.subplots_adjust(right=0.78)


    def nyquist(self, test_current_id, live_results, current_results, len_measurement_queue):
        """
        Plots a Nyquist plot (imaginary part over real part, equal axis scaling).
        The figure is created once; afterwards only the data of the lines is replaced.

        Args:
            test_current_id (str): Id of the current measurement point (e.g. ``"1.5"``).
            live_results (dict): Newest results (keys ``id``, ``real``, ``imag``, ``frequencies``).
            current_results (list[dict]): All results of the current measurement cycle.
            len_measurement_queue (int): Number of measurement setups per cycle.
        """
        # get processed data
        self.processing_results(test_current_id=test_current_id, live_results=live_results,
                                current_results=current_results,
                                len_measurement_queue=len_measurement_queue)

        # only create the figure if it doesn't exist or has been closed
        if self.fig_nyq is None or not plt.fignum_exists(self.fig_nyq.number):
            self._init_nyquist_plot()

        # live results: Z_imag over Z_real
        self.line_nyq.set_data(self.real, self.imag)

        # past results
        if self.past_real:
            self.line_past_nyq.set_data(self.past_real, self.past_imag)
        else:
            self.line_past_nyq.set_data([], [])

        # autoscale
        self.ax_nyq.relim()
        self.ax_nyq.autoscale_view()

        #draw fig
        self.fig_nyq.canvas.draw()
        self.fig_nyq.canvas.flush_events()

    def _init_bode_plot(self):
        """
        initializes the Bode plot with two subplots: magnitude and phase.
        
        """
        self.fig_bode, (self.ax_mag_bode, self.ax_phase_bode) = plt.subplots(
            2, 1, sharex=True, figsize=(10, 6),
            gridspec_kw={'height_ratios': [1, 1], 'hspace': 0.08},
        )

        self.line_past_mag, = self.ax_mag_bode.plot([], [], 'o', color='gray', alpha=0.3, markersize=4)
        self.line_past_phase, = self.ax_phase_bode.plot([], [], 's', color='gray', alpha=0.3, markersize=4)
        self.line_mag, = self.ax_mag_bode.plot([], [], '-o', color='b', label=r'Impedance $|Z|$')
        self.line_phase, = self.ax_phase_bode.plot([], [], '-s', color='r', label=r'Phase $\phi$')

        self.ax_mag_bode.set_title('Bode Plot')
        self.ax_mag_bode.set_ylabel(r'Magnitude $|Z|$ ($\Omega$)')
        self.ax_mag_bode.set_xscale('log')
        self.ax_mag_bode.ticklabel_format(axis='y', style='plain', useOffset=False)

        self.ax_phase_bode.set_ylim(-190, 190)
        self.ax_phase_bode.set_yticks(range(-180, 181, 90))
        self.ax_phase_bode.set_xlabel('Frequency $f$ (Hz)')
        self.ax_phase_bode.set_ylabel(r'Phase $\phi$ (degrees)')

        for ax in (self.ax_mag_bode, self.ax_phase_bode):
            ax.grid(True, which='both', alpha=0.3)
            ax.tick_params(which='both', direction='in', top=True, right=True)

        self.fig_bode.legend(
            handles=[self.line_mag, self.line_phase],
            loc='center left', bbox_to_anchor=(0.8, 0.5),
            title='Legend', frameon=True,
        )
        self.fig_bode.subplots_adjust(right=0.78)
    
    def bode(self, test_current_id, live_results, current_results, len_measurement_queue):
        """Wird in der Schleife aufgerufen: nur Daten austauschen."""
        #get processed data
        self.processing_results(test_current_id = test_current_id,live_results = live_results, current_results = current_results, len_measurement_queue = len_measurement_queue)
        #only create the figure if it doesn't exist or has been closed
        if not hasattr(self, 'fig_bode') or not plt.fignum_exists(self.fig_bode.number):
            self._init_bode_plot()

        #live results
        #Calculate magnitude |Z| and phase from real and imaginary parts
        impedance = [math.hypot(r, i) for r, i in zip(self.real, self.imag)]
        phase = [math.degrees(math.atan2(i, r)) for r, i in zip(self.real, self.imag)]
        self.line_mag.set_data(self.frequencies, impedance)
        self.line_phase.set_data(self.frequencies, phase)

        #past results
        if getattr(self, 'past_real', None):
            past_impedance = [math.hypot(r, i) for r, i in zip(self.past_real, self.past_imag)]
            past_phase = [math.degrees(math.atan2(i, r)) for r, i in zip(self.past_real, self.past_imag)]
            self.line_past_mag.set_data(self.past_frequencies, past_impedance)
            self.line_past_phase.set_data(self.past_frequencies, past_phase)
        else:
            self.line_past_mag.set_data([], [])
            self.line_past_phase.set_data([], [])

        
        #autoscale axis
        self.ax_mag_bode.relim()
        self.ax_mag_bode.autoscale_view()

        self.fig_bode.canvas.draw()
        self.fig_bode.canvas.flush_events()

        