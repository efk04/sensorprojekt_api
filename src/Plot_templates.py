"""
Class that contains plot templates for
Impedanz-frequency-plot
Nyquist-Plot
Bode-Plot
"""
#Imports
import matplotlib.pyplot as plt
import math

class plot_templates:

    def __init__(self):
        #self.fig = plt.figure(figsize=(10,5))
        self.fig = None
        self.ax1 = None
        self.ax2 = None
        self.line_mag = None
        self.line_phase = None


    def impedance_frequency_plot(self, frequency, freq_id, real, imag):
        #get data
        line_real, = plt.plot(frequency, real, 'ro', color='g', label='Real part')
        line_imag, = plt.plot(frequency, imag, 'bs', color='b', label='Imaginary part')
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
       
    
    def nyquist_plot(self, real, imag):
            # Nyquist-Plot: Z_imag vs Z_real 
            line_nyquist = plt.plot(real, imag, 'ro', color='b', label='Nyquist data')
            
            # Wissenschaftliches Styling
            plt.xlabel('Real part $Z_{real}$ / $\\Omega$')
            plt.ylabel('Imaginary part $Z_{imag}$ / $\\Omega$')
            plt.title('Nyquist Plot')
            #
            plt.axhline(0, color='black', linewidth=0.8, linestyle='-')
            plt.axvline(0, color='black', linewidth=0.8, linestyle='-')
            max_val = max(max(abs(r) for r in real), max(abs(i) for i in imag)) * 1.15
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

    def bode_plot(self, frequency, real, imag):
        """
        Create or update a Bode plot (magnitude + phase) on one figure
        with two parallel y-axes (twinx)
        """
        #Calculate magnitude |Z| and phase from real and imaginary parts
        impedance = [math.hypot(r, i) for r, i in zip(real, imag)]
        phase = [math.degrees(math.atan2(i, r)) for r, i in zip(real, imag)]

        if not plt.get_fignums():
            fig, ax1 = plt.subplots(figsize=(8,6))
            ax2 = ax1.twinx()          # create the second axis only once
        else:
            fig = plt.gcf()
            ax1, ax2 = fig.axes[0], fig.axes[1]   # reuse both existing axes


        #Left Y-Axis: Magnitude |Z| 
        line_mag, = ax1.plot(frequency, impedance, 'o', color='b', label='Magnitude (|Z|)')
        ax1.set_xlabel('Frequency $f$ (Hz)')
        ax1.set_ylabel(r'Magnitude $|Z|$ ($\Omega$)', color='b')
        ax1.tick_params(axis='y', labelcolor='b', direction='in')
        ax1.set_xscale('log')
        ax1.grid(True, which='both', alpha=0.3)
        ax1.tick_params(direction='in', which='both', top=True)
        #ax1.legend(loc='upper left')
        
        #Right Y-Axis: Phase
        line_phase, = ax2.plot(frequency, phase, 's', color='r', label=r'Phase ($\phi$)')
        ax2.set_ylabel(r'Phase $\phi$ (degrees)', color='r')
        ax2.tick_params(axis='y', labelcolor='r', direction='in')
        
        
        ax1.set_title('Bode Plot')
        fig.legend(
                handles=[line_mag, line_phase],
                labels=[r'Impedance $|Z|$', r'Phase $\phi$'],
                loc='upper right',    
                bbox_to_anchor=(-0.1,-0.1), 
                title='Legend',
                frameon=True
            )
        #fig.tight_layout()
        plt.show()