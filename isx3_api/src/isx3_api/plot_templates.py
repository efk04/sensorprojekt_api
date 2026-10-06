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


    def processing_results(self, live_results, current_results, len_measurement_queue):
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
        self.freq_id = live_results["id"]
        self.real = live_results["real"]
        self.imag = live_results["imag"]
        self.frequencies = live_results["frequencies"]

        
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
                # read evry dict in the sublist and extend the corresponding lists
                    for item in sublist:

                        if 'id' in item:
                            self.past_id.extend(item['id'])
                        if 'real' in item:
                            self.past_real.extend(item['real'])
                        if 'imag' in item:
                            self.past_imag.extend(item['imag'])
                        if 'frequencies' in item:
                            self.past_frequencies.extend(item['frequencies'])
                        
        




    def impedance_frequency(self, live_results, current_results, len_measurement_queue):
        """
        Plots the real and imaginary part of the impedance over the frequency (log scale).

        Args:
            live_results (dict): Newest results (keys ``id``, ``real``, ``imag``, ``frequencies``).
            current_results (list[dict]): All results of the current measurement cycle.
            len_measurement_queue (int): Number of measurement setups per cycle.
        """

        #get processed data
        self.processing_results(live_results = live_results, current_results = current_results, len_measurement_queue = len_measurement_queue)

        #live results
        line_real, = plt.plot(self.frequencies, self.real, 'ro', color='r', label='Real part')
        line_imag, = plt.plot(self.frequencies, self.imag, 'bs', color='b', label='Imaginary part')
        
        #past results
        if hasattr(self, 'past_real') and self.past_real:
            for p_freq, p_r, p_i in zip(self.past_frequencies, self.past_real, self.past_imag):
                plt.plot(p_freq, p_r, 'o', color='gray', alpha=0.3, markersize=4)  
                plt.plot(p_freq, p_i, 's', color='gray', alpha=0.3, markersize=4)
                
        #decorate plot
        plt.xscale('log')                      
        plt.xlabel('Frequency $f$ / Hz')        
        plt.ylabel('Impedance $Z$ / $\\Omega$') 
        plt.title('Impedance as a Function of Frequency')  
        plt.grid(True, which="both", ls="--", alpha=0.3)
        plt.tick_params(direction='in', which='both', top=True, right=True)
        plt.legend(
            handles=[line_real, line_imag],
            labels=[r'$Z_{real}$', r'$Z_{imag}$'],
            loc='center left',     
            bbox_to_anchor=(1.02, 0.5),  
            title='Legend',
            frameon=True
        )
        #move plot to the right to show the legend
        plt.subplots_adjust(right=0.8)

        
        plt.show()
       
    
    def nyquist(self, live_results, current_results, len_measurement_queue):
        """
        Plots a Nyquist plot (imaginary part over real part, equal axis scaling).

        Args:
            live_results (dict): Newest results (keys ``id``, ``real``, ``imag``, ``frequencies``).
            current_results (list[dict]): All results of the current measurement cycle.
            len_measurement_queue (int): Number of measurement setups per cycle.
        """

        #get processed data
        self.processing_results( live_results = live_results, current_results = current_results, len_measurement_queue = len_measurement_queue)
        
        # Nyquist-Plot: Z_imag vs Z_real
        # live results
        line_nyquist = plt.plot(self.real, self.imag, 'ro', color='b', label='Nyquist data')

        #past results
        if hasattr(self, 'past_real') and self.past_real:
            for p_real, p_imag in zip(self.past_real, self.past_imag):
                plt.plot(p_real, p_imag, 'o', color='gray', alpha=0.3, markersize=4)
        
        # Wissenschaftliches Styling
        plt.xlabel('Real part $Z_{real}$ / $\\Omega$')
        plt.ylabel('Imaginary part $Z_{imag}$ / $\\Omega$')
        plt.title('Nyquist Plot')
        #
        plt.axhline(0, color='black', linewidth=0.8, linestyle='-')
        plt.axvline(0, color='black', linewidth=0.8, linestyle='-')
        max_val = max(max(abs(r) for r in self.real), max(abs(i) for i in self.imag)) * 1.15
        # Important for Nyquist-Plot: keep equal ratio of Y- and X-Axis 
        plt.gca().set_aspect('equal', adjustable='box')
        
        plt.grid(True, which="both", ls="--", alpha=0.3)
        plt.tick_params(direction='in', which='both', top=True, right=True)
        
        plt.legend(
            handles=[line_nyquist],
            labels=[r'$Z_{imag}$ vs $Z_{real}$'],
            loc='center left',    
            bbox_to_anchor=(1.02, 0.5),  
            title='Legend',
            frameon=True
        )
        
        plt.subplots_adjust(right=0.8)
        plt.show()


    def bode(self, live_results, current_results, len_measurement_queue):
        """
        Create or update a Bode plot (magnitude + phase) on one figure
        with two parallel y-axes (twinx).

        Magnitude :math:`|Z|` and phase :math:`\\phi` are calculated from the
        real and imaginary part.

        Args:
            live_results (dict): Newest results (keys ``id``, ``real``, ``imag``, ``frequencies``).
            current_results (list[dict]): All results of the current measurement cycle.
            len_measurement_queue (int): Number of measurement setups per cycle.
        """
        #get processed data
        self.processing_results(live_results = live_results, current_results = current_results, len_measurement_queue = len_measurement_queue)
        
        #checks if a plot exists
        if not plt.get_fignums() or len(plt.get_figlabels() or [1]) == 0:
                    fig, ax1 = plt.subplots(figsize=(12, 6))
                    ax2 = ax1.twinx()
                    
        else:
            
            fig = plt.figure(plt.get_fignums()[0]) 
            
            if len(fig.axes) < 2:
                ax1 = fig.axes[0] if fig.axes else fig.add_subplot(111)
                ax2 = ax1.twinx()
            else:
                ax1, ax2 = fig.axes[0], fig.axes[1]

        #live results  
        #Calculate magnitude |Z| and phase from real and imaginary parts
        impedance = [math.hypot(r, i) for r, i in zip(self.real, self.imag)]
        phase = [math.degrees(math.atan2(i, r)) for r, i in zip(self.real, self.imag)]
        #Left Y-Axis: Magnitude |Z|
        line_mag, = ax1.plot(self.frequencies, impedance, 'o', color='b', label='Magnitude (|Z|)')
        #Right Y-Axis: Phase
        line_phase, = ax2.plot(self.frequencies, phase, 's', color='r', label=r'Phase ($\phi$)')


        #past results
        if hasattr(self, 'past_real') and self.past_real:
            #calculate past impedance and phase
            past_impedance = [math.hypot(r, i) for r, i in zip(self.past_real, self.past_imag)]
            past_phase = [math.degrees(math.atan2(i, r)) for r, i in zip(self.past_real, self.past_imag)]
            #draw plot
            ax1.plot(self.past_frequencies, past_impedance, 'o', color='gray', alpha=0.3, markersize=4)
            ax2.plot(self.past_frequencies, past_phase, 's', color='gray', alpha=0.3, markersize=4)

        
        #Left Y-Axis: Magnitude/impedance |Z|
        ax1.set_title('Bode Plot')
        ax1.set_xlabel('Frequency $f$ (Hz)')
        ax1.set_ylabel(r'Magnitude $|Z|$ ($\Omega$)', color='b')
        ax1.tick_params(axis='y', labelcolor='b', direction='in')
        ax1.set_xscale('log')
        ax1.ticklabel_format(axis='y', style='plain', useOffset=False)
        ax1.grid(True, which='both', alpha=0.3)
        ax1.tick_params(direction='in', which='both', top=True)
        #ax1.legend(loc='upper left')
        #Right Y-Axis: Phase
        ax2.set_ylabel(r'Phase $\phi$ (degrees)', color='r')
        ax2.tick_params(axis='y', labelcolor='r', direction='in')
        
        
        
        fig.legend(
            handles=[line_mag, line_phase],
            labels=[r'Impedance $|Z|$', r'Phase $\phi$'],
            loc='center left',    
            bbox_to_anchor=(0.7, 0.5),  # Platziert die Legende exakt im freien Bereich rechts
            title='Legend',
            frameon=True
        )

        plt.subplots_adjust(right=0.68)
        plt.show()