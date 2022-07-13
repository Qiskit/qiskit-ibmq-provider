# This code is part of Qiskit.
#
# (C) Copyright IBM 2022.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""A module for visualizing device coupling maps"""

from enum import Enum
from datetime import datetime
import asyncio
import json
import ssl
import zlib
from io import BytesIO
from base64 import b64encode
import logging
import pytz
from websocket import WebSocketApp
import ipywidgets as widgets
import numpy as np
from sklearn.decomposition import PCA
from qiskit.providers.jobstatus import JobStatus
from qiskit.providers.fake_provider.fake_backend import FakeBackend

# PLOTS
ENABLE_LEVEL_0 = False
ENABLE_LEVEL_1 = True
JOB_UPDATE_FREQ = 1  # Time to refresh the jobs list

# PLOTS VISUAL STYLE
P_LEFT = 0.125  # the left side of the subplots of the figure
P_RIGHT = 0.2  # the right side of the subplots of the figure
P_BOTTOM = 0.1  # the bottom of the subplots of the figure
P_TOP = 0.7  # the top of the subplots of the figure
P_WSPACE = 0.2  # the amount of width reserved for blank space between subplots
P_HSPACE = 0.4  # the amount of height reserved for white space between subplots
DEFAULT_PLOT_LIMIT = 10
DEFAULT_PLOT_MARGIN = 0.1
LINEWIDTH = 1

# WIDGETS STYLE
JOBS_CB_WIDTH = 310
CHANNEL_DD_WIDTH = 120
PROGRESS_WIDTH = 300


logger = logging.getLogger(__name__)


class CarbonColors(str, Enum):
    """Carbon Design Colors"""

    GRAY20 = "#E0E0E0"
    GRAY60 = "#6F6F6F"
    GRAY80 = "#393939"
    PURPLE60 = "#8A3FFC"
    PURPLE70 = "#6929C4"
    CYAN60 = "#0072C3"
    RED60 = "#DA1E28"
    GREEN50 = "#24A148"
    WHITE = "#FFFFFF"
    CLEAR = "#0000"
    BLACK = "#000"


class LiveDataKeys(str, Enum):
    """Live data dictionary keys"""

    LEVEL_0 = "avgLevel0"
    LEVEL_1 = "avgLevel1"
    ROUNDS = "rounds"
    TOTAL_ROUNDS = "total_rounds"


def is_qlab_notebook():
    """Check if running from Quantum Lab"""
    import os

    client = os.getenv("QE_CUSTOM_CLIENT_APP_HEADER", "")
    return "quantum-computing.ibm.com" in client


class LiveDataVisualization:
    """Live Data Visualization

    This class draws the data generated from the Q instruments

    """

    def __init__(self):
        self.graphs = []

        self.widget = None
        self.backend = None
        self.figsize = None
        self.show_title = None

        # Views
        self.plotview = None
        self.ldata_details = None
        self.job_information_view = None

        self.jobs = []
        self.job_ids = []
        self.selected_job = None
        self.jobs_combo = None

        self.ws_connection = None
        self.ws_task = None

        self.is_quantumlab = is_qlab_notebook()

    # JOB INFO
    def new_selected_job(self, job) -> None:
        """Change the selected job

        Args:
            job (Qiskit Job): Job to be selected
        """
        self.selected_job = job
        if self.job_information_view is not None:
            self.job_information_view.set_job(job)

    def update_job_selector_combobox(self, change) -> None:
        """Change the selected Job from combobox widget"""
        if change["type"] == "change" and change["name"] == "value":
            selected_job = change["new"]
            self.jobs_combo.value = selected_job
            selected_job_idx = self.job_ids.index(selected_job)
            if selected_job not in self.jobs_combo.options:
                self.jobs_combo.options = self.job_ids
            self.new_selected_job(self.jobs[selected_job_idx])
            self.update_websocket_connection()

    def get_livedata_jobs(self) -> list:
        """Get a list of jobs that include LiveData enabled for the current backend
        The list received includes objects with the jobs' info is a dict composed
        by the fields: 'id', 'liveDataEnabled', 'creationDate'.
        The objects included in the list are not same as a Qiskit Job"""
        provider = self.backend.provider()
        livedata_jobs = []

        if provider is not None and not isinstance(provider.backend, FakeBackend):
            total_jobs = provider.backend.job_ids(limit=0)
            livedata_jobs = [job for job in total_jobs if getattr(job, "liveDataEnabled", True)]
            self.job_ids = list(map(lambda x: x["id"], livedata_jobs))
        return livedata_jobs

    def update_websocket_connection(self) -> None:
        """Disconnect websocket from current job and create a new connection"""
        self.disconnect_ws()
        self.ws_task = asyncio.ensure_future(self.init_websockets())
        self.ldata_details.clear()
        self.job_information_view.reset_progress_bar_widget()

    # Viewcomponents

    def jobs_combobox(self) -> widgets.Combobox:
        """Create the Job search Combobox"""
        layout = widgets.Layout(
            display="flex", justify_content="flex-start", width=f"{JOBS_CB_WIDTH}px",
            border=f"solid 1px {CarbonColors.BLACK}"
        )
        jobs_combobox = widgets.Combobox(
            placeholder="Job ID",
            options=self.job_ids,
            ensure_option=True,
            disabled=False,
            layout=layout,
        )
        jobs_combobox.observe(self.update_job_selector_combobox)
        return jobs_combobox

    def setup_views(self) -> None:
        """Compose the widgets inside a parent widget"""

        # Jobs selection
        sjob_title = self.create_title("Job selection")
        label = widgets.Label(value="Job:")
        self.jobs_combo = self.jobs_combobox()
        layout = widgets.Layout(overflow_y="hidden", min_height="32px")
        combo_view = widgets.HBox(children=(label, self.jobs_combo), layout=layout)

        # Jobs info
        job_title = self.create_title("Job information", extra_space=True)
        self.job_information_view = JobInformationView(backend=self.backend, job=self.selected_job)
        job_info = self.job_information_view.widget()

        # Plots
        ldata_title = self.create_title("Live data details", extra_space=True)
        self.ldata_details = LivePlot(self.figsize)
        ldata_details = self.ldata_details.widget()

        self.widget.children = [
            sjob_title,
            combo_view,
            job_title,
            job_info,
            ldata_title,
            ldata_details,
        ]

    # pylint: disable=missing-param-doc,missing-type-doc
    def create_visualization(self, backend, figsize, show_title) -> widgets.VBox:
        """Create the view area with the required elements

        Args:
            backend (Qiskit object): The used backend
            figsize (int, int): size of the area to draw the figures
            show_title (bool): Enable the title in the visualiztion

        Return:
            widgets.VBox A vertical box containing the placeholder for the
                    jobs dropdown and the plot area.
        """

        self.backend = backend
        self.figsize = figsize
        self.show_title = show_title

        self.jobs = self.get_livedata_jobs()

        dropdown_box = widgets.HBox()
        output = widgets.Output(layout=widgets.Layout(display="flex-inline", align_items="center"))

        self.widget = widgets.VBox(children=(dropdown_box, output))

        if not isinstance(self.backend, FakeBackend):
            self.setup_views()

        # Update Jobs
        asyncio.ensure_future(self.update_job_loop())

        # Connect to the first job
        if len(self.jobs) > 0:
            selected_job = self.jobs_combo.options[0]
            self.jobs_combo.value = selected_job
            selected_job_idx = self.job_ids.index(selected_job)
            self.new_selected_job(self.jobs[selected_job_idx])
            self.update_websocket_connection()

        return self.widget

    def create_title(self, title, extra_space: bool = False) -> widgets.HTML:
        """Create an HTML Ipywidget to be used as a title

        Args:
            title (str): Text to be used as a title
            extra_space (bool): Add some vertical space befor the title

        Return:
            (Ipywidget): HTML widget used as title

        """
        margin = "34px" if extra_space is True else "8px"
        content = f"<h5 style='margin-top: {margin};margin-bottom: 8px;'><b>{title}</b></h5>"
        return widgets.HTML(value=content)

    # Data management
    def pako_inflate(self, data) -> str:
        """Decompress data with zlib

        Args:

            data (binary): compressed data in binary format

        Returns:

            (decompressed_data): Decompressed json object as string

        """
        decompress = zlib.decompressobj(15)
        decompressed_data = decompress.decompress(data)
        decompressed_data += decompress.flush()
        decompressed_data = json.loads(decompressed_data)
        return decompressed_data

    # Websockets
    def ws_on_open(self, ws_connection) -> None:
        """Send the opening message

        Args:

            ws_connection (object): websocket connection

        """
        logger.debug("Sending opening message")
        ws_connection.send(
            json.dumps(
                {
                    "type": "authentication",
                    "data": self.backend.provider().credentials.access_token,
                }
            )
        )
        logger.debug("opening message sent")

    def ws_on_message(self, ws_connection, message) -> None:
        """Process the received data

        Args:

            ws_connection (object): websocket connection

            message (bytes) : received messages

        """
        logger.debug("RECEIVE PACKAGE")
        compressed_msg = json.loads(message)
        if compressed_msg["type"] == "live-data":
            logger.debug("📝 ws@job_id #%s received a msg!", self.selected_job['id'])
            result = self.pako_inflate(bytes(compressed_msg["data"]["data"]))
            # Check result type. In the last package it is a list instead a dict.
            if self.ldata_details:
                self.ldata_details.draw_data(result)
                self.ldata_details.show()
            if self.job_information_view:
                value = result.get(
                    self.ldata_details._selected_channel,
                    self.ldata_details._channels[0],
                ).get("rounds", 0)
                max_value = result.get("total_rounds")
                self.job_information_view.update_progress_bar_widget(
                    max_value=max_value, value=value
                )

            ws_connection.send(json.dumps({"type": "client", "data": "release"}))
        logger.debug("End on_message")

    def ws_run_forever(self) -> None:
        """Calls the websocket-client run_forever method with parameters

        """
        return self.ws_connection.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    async def init_websockets(self) -> None:
        """Init Websockets using Websockets library

        """
        uri: str = (f"{self.backend.provider().credentials.websockets_url}"
                    f"jobs/{self.selected_job['id']}/live_data")
        logger.debug("🔌 ws@job_id #%s connecting to %s", self.selected_job['id'], uri)
        this_ws = None
        try:
            # pylint: disable=E1101
            logger.debug("Opening WebsocketApp")
            ws_connection = WebSocketApp(uri,
                                         on_open=self.ws_on_open,
                                         on_message=self.ws_on_message)
            self.ws_connection = ws_connection
            this_ws = ws_connection
            logger.debug("Connection established")
            await asyncio.get_event_loop().run_in_executor(None, self.ws_run_forever)
            logger.debug("Running forever")

        except BaseException as error:
            logger.debug("💥 ws@job_id #%s errored/closed: %s", self.selected_job['id'], error)
            if self.ws_connection == this_ws:
                logger.debug("🤖 Trying to reconnect ws@job_id #%s...", self.selected_job['id'])
                await self.init_websockets()

    def disconnect_ws(self) -> None:
        """Close the websocket connection"""
        self.ldata_details.hide()
        if self.ws_task:
            self.ws_task.cancel()
        if self.ws_connection:
            self.ws_connection.close()
            self.ws_connection = None

    async def update_job_loop(self) -> None:
        """Loop to keep the job list and the job information updated"""
        while self.widget:
            previous_len = len(self.jobs)
            self.jobs = self.get_livedata_jobs()
            new_len = len(self.jobs)
            if len(self.jobs) > 0:
                self.jobs_combo.options = self.job_ids
                if self.jobs_combo.value != "":
                    if previous_len == new_len:
                        self.job_information_view.set_job(
                            self.jobs[self.job_ids.index(self.jobs_combo.value)]
                        )
                    else:
                        logger.debug("changing job to the new received: %s", self.job_ids[0])
                        self.jobs_combo.value = self.job_ids[0]
                        self.job_information_view.set_job(self.jobs[0])  # new job arrived, take it
                else:
                    self.jobs_combo.value = self.job_ids[0]
                    self.job_information_view.set_job(self.jobs[0])
            await asyncio.sleep(JOB_UPDATE_FREQ)


class LivePlot:
    """Live data details component"""

    def __init__(self, figsize) -> None:
        self._channels = []
        self._channels_dd = None
        self._selected_channel = 0

        # Plots
        self._raw_plot = None
        self._iq_plot = None
        self._signal_plot = None
        self._oq_plot = None

        self._data = None
        self._graphs = None
        self.figsize = figsize
        self.fig_generated = False
        self.fig = None
        self._plotview = None

        self.view = None

    def clear(self) -> None:
        """Clean up all the class values"""
        self._channels = []

        self._raw_plot = None
        self._iq_plot = None
        self._signal_plot = None
        self._oq_plot = None

        self._data = None
        self._graphs = None
        self.fig = None
        self.fig_generated = False

    def get_plotview_height(self):
        """Calculate the required heigth to display the plots properly"""
        dropdown_height = 60
        plot_row_height = 300
        rows = [ENABLE_LEVEL_0, ENABLE_LEVEL_1]

        return dropdown_height + sum(rows) * plot_row_height

    def widget(self) -> widgets:
        """Create the live plot area widgets"""
        channels_label = widgets.Label(value="Channel:")
        self._channels_dd = self.channels_dropdown()
        combo_view = widgets.HBox(children=(channels_label, self._channels_dd))

        self._plotview = widgets.HTML(
            layout=widgets.Layout(display="flex-inline", align_items="center")
        )
        box_height = self.get_plotview_height()
        box_layout = widgets.Layout(
            display="flex-inline", margin="0px", min_height=f"{box_height}px"
        )
        self.view = widgets.VBox(children=(combo_view, self._plotview), layout=box_layout)

        return self.view

    def hide(self) -> None:
        """Hide the LivePlot widget"""
        if self.view:
            self.hide_plot()
            self.view.layout.visibility = "hidden"

    def show(self) -> None:
        """Show the LivePlot widget"""
        if self.view:
            self.view.layout.visibility = "visible"

    def hide_plot(self) -> None:
        """Hide the LivePlot area"""
        if self._plotview:
            self._plotview.layout.visibility = "hidden"

    def show_plot(self) -> None:
        """Show the LivePlot area"""
        if self._plotview:
            self._plotview.layout.visibility = "visible"

    # Channels Dropdown
    def channels_dropdown(self) -> widgets.Dropdown:
        """Create the dropdown for channel selection"""
        layout = widgets.Layout(
            border_style="solid",
            display="flex",
            justify_content="flex-start",
            width=f"{CHANNEL_DD_WIDTH}px",
        )
        channels_dropdown = widgets.Dropdown(options=self._channels, description="", layout=layout)
        channels_dropdown.observe(self.update_channel_selector)
        return channels_dropdown

    def update_channel_selector(self, change) -> None:
        """Change the selected channel from the dropdown"""
        if change["type"] == "change" and change["name"] == "value":
            self._selected_channel = change["new"]
            self.reset_all_view_limits()
            self.draw_data()

    def update_channel_dd_content(self, data) -> None:
        """Update the channel dropdown with the received data"""
        current_selected_channel = self._selected_channel
        channels = self.get_channels_list(data)
        self._channels_dd.options = channels
        if current_selected_channel in channels:
            self._selected_channel = current_selected_channel
            self._channels_dd.value = channels[channels.index(current_selected_channel)]
        else:
            self._channels_dd.value = channels[0]

    # Draw data
    def draw_data(self, data=None) -> bool:
        """Call the draw routines"""
        if data is None and self._data is None:
            return False

        if data is not None:
            self._data = data

        if self.fig_generated:
            self.update_live_data(self._data)
        else:
            # logger.debug("Generating image")
            self.setup_live_data_plots(self._data)

        self.show_plot()

        return True

    def fig_to_base64(self, fig) -> bytes:
        """Transform a Matplotlib fig into its Base64-encoded bytes representation

        Args:
            fig (~matplotlib.figure.Figure): the Matplotlib figure to transform.

        Returns:
            The figure encoded in Base64
        """
        img = BytesIO()
        fig.savefig(img, format="png", bbox_inches="tight")
        img.seek(0)

        return b64encode(img.getvalue())

    def setup_live_data_plots(self, data) -> None:
        """Plots the error map of a given backend.

        Args:
            data (dict): information to be plotter.

        """
        from matplotlib import get_backend
        import matplotlib.pyplot as plt

        self.update_channel_dd_content(data)

        l0a = None
        l0b = None
        l1a = None
        l1c = None
        l1d = None

        # PLOT
        l0_height = 3.8 if ENABLE_LEVEL_0 is True else 0
        l1_height = 3.8 if ENABLE_LEVEL_1 is True else 0

        fig_size = self.figsize[0], l0_height + l1_height

        plt.rcParams.update(
            {
                "font.weight": "normal",
                "xtick.major.size": 5,
                "xtick.major.pad": 7,
                "xtick.labelsize": 12,
                "grid.color": CarbonColors.GRAY20.value,
                "grid.linestyle": "-",
                "grid.linewidth": 0.5,
                "lines.linewidth": 2,
                "lines.color": CarbonColors.GRAY20.value,
            }
        )

        # Prevents that matplotlib drawing figures in the cell's execution output
        plt.ioff()

        fig = plt.figure(constrained_layout=True, figsize=fig_size)

        mosaic_grid = []
        level_0_row = ["l0", "l0", "l0"]
        level_1_row = ["l1a", "l1b", "l1c"]
        if ENABLE_LEVEL_0:
            mosaic_grid.append(level_0_row)
        if ENABLE_LEVEL_1:
            mosaic_grid.append(level_1_row)

        ax_dict = fig.subplot_mosaic(
            mosaic_grid,
            gridspec_kw={
                "bottom": P_BOTTOM,
                "top": P_TOP,
                "left": P_LEFT,
                "right": P_RIGHT,
                "wspace": P_WSPACE,
                "hspace": P_HSPACE,
            },
        )
        n_circuits = self.get_circuits_number(data, self._selected_channel)

        # PLOT L0
        if ENABLE_LEVEL_0:
            data_l0a = self.get_l0_data(data, self._selected_channel)
            l0a, l0b = self.plot_raw_data(ax_dict["l0"], data_l0a, n_circuits)

        # L1
        if ENABLE_LEVEL_1:
            real_list, imag_list = self.get_l1_data(data, self._selected_channel)
            l1a = self.plot_iq_complex_plane(ax_dict["l1a"], real_list, imag_list)
            l1b, l1c = self.plot_signal_circuit(ax_dict["l1b"], real_list, imag_list, n_circuits)
            l1d = self.plot_optimal_quadrature(ax_dict["l1c"], real_list, imag_list, n_circuits)

        self._graphs = [l0a, l0b, l1a, l1b, l1c, l1d]

        if get_backend() in ["module://ipykernel.pylab.backend_inline", "nbAgg"]:
            plt.close(fig)

        self.fig = fig
        self.fig_generated = True

        encoded = self.fig_to_base64(fig)
        html_image = '<img src="data:image/png;base64, {}">'.format(encoded.decode("utf-8"))
        self._plotview.value = html_image

    def update_live_data(self, data) -> None:
        """Update the plots with the received data

        Args:
            data (dict): Live-data object received from websocket
        """
        if self.widget is None or self.fig is None:
            return

        n_circuits = self.get_circuits_number(data, self._selected_channel)

        l0a = self._graphs[0]
        l0b = self._graphs[1]
        l1a = self._graphs[2]
        l1b = self._graphs[3]
        l1c = self._graphs[4]
        l1d = self._graphs[5]

        if ENABLE_LEVEL_0:
            data_l0a = self.get_l0_data(data, self._selected_channel)
            plot_data_l0b = None
            if n_circuits > 1:
                plot_data_l0b = data_l0a[-1]

            plot_data_l0a = data_l0a[0]

            total_data = len(plot_data_l0a)
            time_value = np.arange(0, total_data, 1)

            l0a.set_data(time_value, plot_data_l0a)
            self.set_view_limits(self._raw_plot, None, plot_data_l0a, center_origin=True)
            if l0b is not None:
                l0b.set_data(time_value, plot_data_l0b)
                self.set_view_limits(self._raw_plot, None, plot_data_l0b, center_origin=True)

        if ENABLE_LEVEL_1:
            real_list, imag_list = self.get_l1_data(data, self._selected_channel)

            # Setup IQ plot scale
            self.set_view_limits(self._iq_plot, real_list, imag_list, center_origin=False)
            view_data = real_list + imag_list
            self.set_view_limits(self._signal_plot, None, view_data, center_origin=True)

            # Update plots

            l1a.set_offsets(np.c_[real_list, imag_list])

            # With 1 circuit only, duplicate the first point to create a line
            if len(real_list) == 1:
                real_list = [real_list[0], real_list[0]]
                imag_list = [imag_list[0], imag_list[0]]

            if n_circuits > 1:
                l1b.set_data(range(n_circuits), real_list)
                l1c.set_data(range(n_circuits), imag_list)
                avg_data_oq = self.get_op_data(real_list, imag_list)
                l1d.set_data(range(n_circuits), avg_data_oq)
                self.set_view_limits(self._oq_plot, None, avg_data_oq)
            else:
                x = [0, 0]
                y = [real_list[0], imag_list[0]]
                l1b.set_offsets(np.c_[x, y])

        encoded = self.fig_to_base64(self.fig)
        html_image = '<img src="data:image/png;base64, {}">'.format(encoded.decode("utf-8"))
        self._plotview.value = html_image

    # Views control
    def reset_all_view_limits(self) -> None:
        """Reset the views scale to the default values"""
        if ENABLE_LEVEL_0:
            self.reset_view_limits(self._raw_plot, reset_x=False)
        if ENABLE_LEVEL_1:
            self.reset_view_limits(self._iq_plot)
            self.reset_view_limits(self._signal_plot, reset_x=False)
            self.reset_view_limits(self._oq_plot, reset_x=False)

    def reset_view_limits(self, view, reset_x: bool = True, reset_y: bool = True) -> None:
        """Reset the view scale

        Args:

            view (object): view to reset the scale

            reset_x (bool): is required to reset the x scale

            reset_y (bool): is required to reset the y scale
        """
        if view is None:
            return
        if reset_x:
            view.set_xlim(-1 * DEFAULT_PLOT_LIMIT, DEFAULT_PLOT_LIMIT)
        if reset_y:
            view.set_ylim(-1 * DEFAULT_PLOT_LIMIT, DEFAULT_PLOT_LIMIT)

    def set_view_limits(self, view, values_x, values_y, center_origin: bool = True) -> None:
        """Set the view scale

        Args:

            view (object): view to set the scale

            values_x (list): values on the x axis

            values_y (list): values on the y axis

            center_origin (bool): center the plot in 0
        """

        def new_limits(new_values, center_origin: bool) -> float:
            """Calculate the new limit to fit all data in the plot

            Args:

                new_values (list): list of values to make them fit

                center_origin (bool): center the plot in 0

            Return:

                - (float, float): new limits <lower, upper>

            """
            new_max = np.max(new_values)
            new_min = np.min(new_values)

            if center_origin:
                new_limit = max(np.abs(new_min), new_max)
                max_limit = new_limit
                min_limit = -1 * max_limit

            else:
                min_limit = new_min
                max_limit = new_max

            return min_limit, max_limit

        if values_x is not None:
            min_x_lim, max_x_lim = new_limits(values_x, center_origin)
            if values_y is None:
                margin = DEFAULT_PLOT_MARGIN * abs(max_x_lim - min_x_lim)
                view.set_xlim(min_x_lim - margin, max_x_lim + margin)
                return

        if values_y is not None:
            min_y_lim, max_y_lim = new_limits(values_y, center_origin)
            if values_x is None:
                margin = DEFAULT_PLOT_MARGIN * abs(max_y_lim - min_y_lim)
                view.set_ylim(min_y_lim - margin, max_y_lim + margin)
                return

        if center_origin:
            res = max(abs(max_x_lim), abs(max_y_lim), abs(min_x_lim), abs(min_y_lim))
            res = DEFAULT_PLOT_MARGIN * res
            view.set_xlim(-1 * res, res)
            view.set_ylim(-1 * res, res)
        else:
            range_x = max_x_lim - min_x_lim
            range_y = max_y_lim - min_y_lim
            margin = abs(max(range_x, range_y)) * DEFAULT_PLOT_MARGIN

            view.set_xlim(min_x_lim - margin, max_x_lim + margin)
            view.set_ylim(min_y_lim - margin, max_y_lim + margin)

    # Plot functionality
    def plot_raw_data(self, view, data, n_circuits) -> tuple:
        """Generate the view for the Level 0 data

        Args:
            view (object): matplotlib subplot
            data (list): level 0 data
            n_circuits (int): Number of circuits

        Returns:
            The level 0 view.

        """
        # L0 - Raw data
        view.set_title("Raw")
        view.set_xlabel("Time (ns)")
        view.grid(True)
        self._raw_plot = view

        plot_data_l0a = data[0]
        total_data = len(plot_data_l0a)

        view.set_xlim(0, total_data)
        self.set_view_limits(view, None, plot_data_l0a)

        (raw_a,) = view.plot(
            plot_data_l0a, label="Circuit 0", color=CarbonColors.PURPLE60.value, linewidth=LINEWIDTH
        )
        raw_b = None
        if n_circuits > 1:
            plot_data_l0b = data[-1]
            view_data = plot_data_l0a + plot_data_l0b
            self.set_view_limits(view, None, view_data, center_origin=True)
            (raw_b,) = view.plot(
                plot_data_l0b,
                label=f"Circuit {n_circuits - 1}",
                color=CarbonColors.CYAN60.value,
                linewidth=LINEWIDTH,
            )
            view.legend(handles=[raw_a, raw_b], loc="upper right", frameon=True)
        return raw_a, raw_b

    def plot_iq_complex_plane(self, view, real_list, imag_list) -> object:
        """Generate the IQ Complex Plane view with the Level 1 data

        Args:
            view (object): matplotlib subplot
            real_list (list): list with the real components of the L1 data
            imag_list (list): list with the imaginary components of the L1 data

        Returns:
            The IQ Complex Plane view.

        """
        # L1 - IQ COMPLEX
        view.set_title("IQ complex plane")
        view.set_xlabel("I [arb units]")
        view.set_ylabel("Q [arb units]")
        view.grid(True)
        self._iq_plot = view

        # Setup IQ plot scale
        self.set_view_limits(view, real_list, imag_list, center_origin=False)

        iq_view = view.scatter(real_list, imag_list, color=CarbonColors.PURPLE70.value)
        if len(real_list) == 1:
            real_list = [real_list[0], real_list[0]]
            imag_list = [imag_list[0], imag_list[0]]

        return iq_view

    def plot_signal_circuit(self, view, real_list, imag_list, n_circuits) -> tuple:
        """Generate the Signal/Circuit view with the Level 1 data

        Args:
            view (object): matplotlib subplot
            real_list (list): list with the real components of the L1 data
            imag_list (list): list with the imaginary components of the L1 data
            n_circuits (int): Number of circuits

        Returns:
            The Signal/Circuit view (object)

        """
        # L1 - Signal vs the circuit index
        view.set_title("Signal vs circuit")
        view.set_xlabel("Circuit #")
        view.set_ylabel("I/Q [arb units]")
        view.grid(True)
        x_max_lim = max(1, n_circuits - 1)
        view.set_xlim(0, x_max_lim)
        values = real_list + imag_list
        self.set_view_limits(view, None, values, center_origin=True)
        self._signal_plot = view

        if n_circuits > 1:
            view.xaxis.set_ticks(range(0, x_max_lim + 1), minor=(n_circuits > 4))
            (sc_a,) = view.plot(
                real_list, label="I", color=CarbonColors.PURPLE60.value, linewidth=LINEWIDTH
            )
            (sc_b,) = view.plot(
                imag_list, label="Q", color=CarbonColors.CYAN60.value, linewidth=LINEWIDTH
            )
            view.legend(handles=[sc_a, sc_b], loc="upper right", frameon=True)
        else:
            view.xaxis.set_ticks(range(0, 1), minor=False)
            x = [0, 0]
            y = [real_list[0], imag_list[0]]
            sc_a = view.scatter(
                x, y, color=[CarbonColors.PURPLE60.value, CarbonColors.CYAN60.value]
            )
            sc_b = None

        return sc_a, sc_b

    def plot_optimal_quadrature(self, view, real_list, imag_list, n_circuits) -> object:
        """Generate the Optimal Quadrature view with the Level 1 data

        Args:
            view (object): matplotlib subplot
            real_list (list): list with the real components of the L1 data
            imag_list (list): list with the imaginary components of the L1 data
            n_circuits (int): Number of circuits

        Returns:
            The Optimal Quadrature view.

        """
        # L1 - Optimal Quadrature vs the circuit index
        view.set_title("Optimal Quadrature\nvs circuit")
        view.set_xlabel("Circuit #")
        view.set_ylabel("Optimal Quadrature [arb units]")
        x_max_lim = max(1, n_circuits - 1)
        view.set_xlim(0, x_max_lim)
        view.grid(True)
        self._oq_plot = view

        if n_circuits > 1:
            view.xaxis.set_ticks(range(0, x_max_lim + 1), minor=(n_circuits > 4))
            avg_data_oq = self.get_op_data(real_list, imag_list)
            self.set_view_limits(view, None, avg_data_oq, center_origin=True)
            (oq_view,) = view.plot(
                avg_data_oq, color=CarbonColors.CYAN60.value, linewidth=LINEWIDTH
            )
        else:
            view.xaxis.set_ticks(range(0, 1), minor=False)
            oq_view = view.scatter(0, 0, color=CarbonColors.CYAN60.value)

        return oq_view

    # Data management
    def get_channels_list(self, data) -> list:
        """Return a sorted list of the available channels

        Args:
            data (dict): Live-data object received from websocket

        Returns:
            Sorted channels list.
        """
        if data:
            channels = list(data.keys())
            channels.remove(LiveDataKeys.TOTAL_ROUNDS.value)
            channels.sort()
            self._selected_channel = channels[0]
            self._channels = channels
            return channels
        return []

    def get_circuits_number(self, data, channel) -> int:
        """Get the number of circuits

        Args:
            data (dict): Live-data object received from websocket
            channel (str): Selecte channel

        Returns:
            Number of circuits (int)

        """
        if ENABLE_LEVEL_1:
            return len(data[channel][LiveDataKeys.LEVEL_1.value])
        elif ENABLE_LEVEL_0:
            return len(data[channel][LiveDataKeys.LEVEL_0.value])
        else:
            return 0

    def get_l0_data(self, data, channel) -> list:
        """Get the Level 0 (raw) data for the selected channel

        Args:
            data (dict): Live-data object received from websocket
            channel (str): Selecte channel

        Returns:
            List with the values for the Level 0 data.
        """
        return data[channel][LiveDataKeys.LEVEL_0.value]

    def get_l1_data(self, data, channel) -> tuple:
        """Get the Level 1 data for the selected channel

        Args:
            data (dict): Live-data object received from websocket
            channel (str): Selecte channel

        Returns:
            Real List, Imaginary List : Values for the Level 1 data.
        """

        l1a_data = data[channel][LiveDataKeys.LEVEL_1.value]
        complex_data = np.array(l1a_data)
        complex_data = complex_data.astype(float)
        return complex_data[:, 0], complex_data[:, 1]

    def get_op_data(self, x_values, y_values) -> list:
        """Calculate the Optimal Quadrature values using the Principal component analysis (PCA)

        Args:
            values_x (list<float>): Values for the x axis (usually real component)
            values_y (list<float>): Values for the y axis (usually imaginary component)

        Return:
            - (list): Principal components
        """
        stacked_data = np.vstack((x_values, y_values)).T
        pca = PCA(n_components=1)
        return pca.fit_transform(stacked_data).flatten()


class ProgressBar:
    """Custom progress bar widget"""

    def __init__(self):
        self._progress_bar = None
        self._percentage = None
        self._widget = None

    def get_widget(self) -> widgets:
        """Return the progrees bar widget"""
        if self._widget is None:
            self.create_progress_bar()
        return self._widget

    def create_progress_bar(self) -> widgets.HBox:
        """Create the progress bar component"""
        self._percentage = widgets.Label(value="0%")
        layout = widgets.Layout(
            display="flex", justify_content="flex-start", width=f"{PROGRESS_WIDTH}px"
        )
        self._progress_bar = widgets.IntProgress(
            value=0,
            min=0,
            max=10,
            description="",
            bar_style="",  # 'success', 'info', 'warning', 'danger' or ''
            style={"bar_color": CarbonColors.CYAN60.value},
            orientation="horizontal",
            layout=layout,
        )

        self._widget = widgets.HBox(children=(self._progress_bar, self._percentage))
        return self._widget

    def update_progress_bar(self, _max: int, _value: int, _min: int = 0) -> None:
        """Update progress bar values

        Args:
            _max (int): max value
            _value (int): current value
            _min (int): min value
        """
        self._progress_bar.min = _min
        self._progress_bar.max = _max
        self._progress_bar.value = _value
        self._percentage.value = f"{int((_value/_max)*100)}%"
        self._progress_bar.style = {"bar_color": CarbonColors.CYAN60.value}

    def reset_progress_bar(self):
        """Reset progress bar"""
        self._progress_bar.min = 0
        self._progress_bar.max = 10
        self._progress_bar.value = 0
        self._percentage.value = "0%"
        self._progress_bar.style = {"bar_color": CarbonColors.CYAN60.value}

    def error_progress_bar(self):
        """Put progress bar in error style"""
        self._percentage.value = "Error"
        self._progress_bar.style = {"bar_color": CarbonColors.RED60.value}

    def complete_progress_bar(self):
        """Update progress bar values to complete (valid state)"""
        self._progress_bar.min = 0
        self._progress_bar.max = 10
        self._progress_bar.value = 10
        self._percentage.value = "100%"
        self._progress_bar.style = {"bar_color": CarbonColors.GREEN50.value}


class JobInformationView:
    """Job Information component"""

    def __init__(self, job, backend) -> None:
        self._backend = backend
        self._progress_bar = ProgressBar()
        self._progress_bar_widget = self._progress_bar.create_progress_bar()
        self._information_view = self.create_job_information_view(job)

    def widget(self) -> widgets.VBox:
        """Create the Job Information widgets"""
        box_layout = widgets.Layout(display="flex-inline", margin="0px")

        return widgets.VBox(
            children=(self._progress_bar_widget, self._information_view), layout=box_layout
        )

    def set_job(self, job) -> None:
        """Fill the job information view

        Args:

            job (Dict with the fields 'id', 'liveDataEnabled' and 'creationDate'): the job to select

        """
        if not job:
            return

        # To get all the information needed, we request the job details to the API
        # The information returned is the type of QiskitJob
        qiskit_job = self._backend.provider().backend.retrieve_job(job_id=job['id'])
        status = qiskit_job.status()
        if status in [JobStatus.RUNNING, JobStatus.DONE]:
            self.show_progress_bar()
        elif status in [JobStatus.VALIDATING, JobStatus.INITIALIZING]:
            self._progress_bar.reset_progress_bar()
            self.show_progress_bar()
        elif status in [JobStatus.ERROR]:
            self._progress_bar.error_progress_bar()
            self.show_progress_bar()
        else:
            self._progress_bar.reset_progress_bar()

        self.information_view.value = self.job_information_content(qiskit_job)

    # Views
    def create_job_information_view(self, job) -> widgets.HTML:
        """Create the job information view"""
        content = self.job_information_content(job)
        layout = widgets.Layout(display="flex", justify_content="flex-start")
        self.information_view = widgets.HTML(value=content, layout=layout)
        return self.information_view

    def job_information_content(self, job) -> str:
        """Create the job information content"""
        content = "<table class='livedata-table'>"
        content += """
            <style>
            .livedata-table {
                border-collapse: collapse;
                width: auto;
                margin-left: 0px;
            }
            .livedata-table td {
                text-align: left;
                height: 6px;
                min-width: 70px;
                padding-left: 0px;
                padding-right: 40px;
                padding-top: 0px;
                padding-bottom: 0px;
            }
        """
        content += f".livedata-table tr td:nth-child(1) {{ color: {CarbonColors.GRAY60.value};}}"
        content += f".livedata-table tr td:nth-child(2) {{ color: {CarbonColors.GRAY80.value};}}"
        content += f".livedata-table tr td:nth-child(4) {{ color: {CarbonColors.GRAY60.value};}}"
        content += f".livedata-table tr td:nth-child(5) {{ color: {CarbonColors.GRAY80.value};}}"
        content += (
            f".livedata-table:nth-child(even) {{ background-color: {CarbonColors.CLEAR.value};}}"
        )
        content += (
            f".livedata-table:nth-child(odd) {{ background-color: {CarbonColors.CLEAR.value};}}"
        )
        content += "</style>"

        content += "<tr class='livedata-table'><td class='livedata-table'>Job status</td>"
        content += f"<td class='livedata-table'>{self.get_job_status(job)}</td>"
        content += "<td class='livedata-table'></td>"
        content += "<td class='livedata-table'>System</td>"
        content += f"<td class='livedata-table'>{self._backend.name()}</td></tr>"

        content += "<tr class='livedata-table'><td class='livedata-table'>Estimated completion</td>"
        content += f"<td class='livedata-table'>{self.get_job_completion_time(job)}</td>"
        content += "<td class='livedata-table'></td>"
        content += "<td class='livedata-table'>Provider</td>"
        content += f"<td class='livedata-table'>{self.get_provider()}</td></tr>"

        content += "<tr class='livedata-table'><td class='livedata-table'>Sent to Queue</td>"
        content += f"<td class='livedata-table'>{self.get_job_sent_queue_time(job)}</td>"
        content += "<td class='livedata-table'></td>"
        content += "<td class='livedata-table'></td></tr>"
        content += "</table>"
        return content

    # Progress bar control
    def update_progress_bar_widget(self, max_value, value) -> None:
        """Update the progress bar values"""
        if self._progress_bar:
            self._progress_bar.update_progress_bar(_max=max_value, _value=value)

    def reset_progress_bar_widget(self) -> None:
        """Reset the progress bar values"""
        if self._progress_bar:
            self._progress_bar.reset_progress_bar()

    def hide_progress_bar(self) -> None:
        """Hide the progress bar"""
        self._progress_bar_widget.layout.visibility = "hidden"

    def show_progress_bar(self) -> None:
        """Show the progress bar"""
        self._progress_bar_widget.layout.visibility = "visible"

    # Data management

    def get_job_status(self, job) -> str:
        """Get the status of the job"""
        if job:
            status = job.status().name
        else:
            status = "-"
        return status

    def get_job_completion_time(self, job) -> str:
        """Get estimated job completion time

        Args:
            job (job): Quantum Job

        Returns:
            (str): Estimated completion time
        """
        if not job:
            return "-"
        job_status = job.status()
        if job_status == JobStatus.DONE:
            self._progress_bar.complete_progress_bar()
            return "Done"
        elif job_status == JobStatus.ERROR:
            self._progress_bar.error_progress_bar()
            return "Error running the job"
        elif job_status in [JobStatus.QUEUED, JobStatus.VALIDATING, JobStatus.INITIALIZING]:
            self._progress_bar.reset_progress_bar()

        try:
            completion_time = job.queue_info().estimated_complete_time
        except BaseException:
            return "..."

        formated_completion = self.format_timedate(completion_time)
        remaining = self.time_to_completion(completion_time)

        return f"{formated_completion} {remaining}"

    def get_provider(self) -> str:
        """Get the provider information from the backend

        Return:
            bi (str): Backend information
        """

        return f"{self._backend.hub}/{self._backend.group}/{self._backend.project}"

    def time_to_completion(self, completion_time: datetime) -> str:
        """Get the estimate remaining time to complete

        Args:
            completion_time (datetime): Date to finish

        Returns:
            (str): Time to complete
        """
        utc = pytz.UTC
        now = datetime.now().replace(tzinfo=utc)
        completion_time = completion_time.replace(tzinfo=utc)

        if now > completion_time:
            return ""
        delta_time = completion_time - now
        days, hours, minutes = self.days_hours_minutes(delta_time)

        hours = (days * 24) + hours
        return f"({hours}:{minutes:02d} remaining)"

    def get_job_sent_queue_time(self, job) -> str:
        """Get the date and time when the job was sent to the queue

        Args:
            job (job): Quantum Job

        Returns:
            (str): Date when added to the queue

        """
        if not job:
            return "-"
        queued_date = job.creation_date()
        return self.format_timedate(queued_date)

    def days_hours_minutes(self, tdelta) -> tuple:
        """Get days, hours and minutes from a timedelta

        Args:
            tdelta (timedelta): Time interval to transform

        Returns:
            (int, int, int): Days, hours and minutes

        """
        return tdelta.days, tdelta.seconds // 3600, (tdelta.seconds // 60) % 60

    def format_timedate(self, date) -> str:
        """Transfrom a date from timedate to a formated string

        Args:
            date (timedate): Date to transform

        Returns:
            (str): Date as formated string

        """

        return date.strftime("%B %d, %Y, %I:%M %p")
