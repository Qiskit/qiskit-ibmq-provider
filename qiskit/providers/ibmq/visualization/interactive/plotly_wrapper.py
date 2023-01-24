# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
# pylint: disable=import-outside-toplevel

"""Plotly class wrappers."""

from typing import Tuple, Optional, Any

import plotly.graph_objects as go

# pylint: disable=abstract-method


class PlotlyFigure:
    """A simple wrapper around ``plotly.graph_objects.Figure`` class.

    This wrapper class allows the figures to be more or less drop in replacements
    for ``matplotlib`` figures. For example, you can use :meth:`savefig()` to
    save the figure.
    """

    def __init__(self, fig: go.Figure):
        """PlotlyFigure class.

        Args:
            fig: Figure to use.
        """
        self._fig = fig

    def __repr__(self):
        return self._fig.__repr__()

    def _ipython_display_(self):
        import plotly.io as pio

        if pio.renderers.render_on_display and pio.renderers.default:
            pio.show(self._fig, config={'displayModeBar': False,
                                        'editable': False})
        else:
            print(repr(self))

    def show(self, *args, **kwargs) -> None:
        """Display the figure.

        Args:
            *args: Variable length argument list to be passed to ``plotly.io.show()``.
            **kwargs: Arbitrary keyword arguments to be passed to ``plotly.io.show()``.
        """
        import plotly.io as pio

        config = {}
        if 'config' not in kwargs.keys():
            config = {'displayModeBar': False,
                      'editable': False}

        pio.show(self._fig, *args, config=config, **kwargs)

    def savefig(
            self,
            filename: str,
            figsize: Tuple[Optional[int]] = (None, None),
            scale: float = 1,
            transparent: bool = False
    ) -> None:
        """Save the figure.

        Args:
            filename: Filename to save to.
            figsize: Figure size (W x H) in pixels.
            scale: Scale of the output figure.
            transparent: Whether to use transparent background.
        """
        if transparent:
            plot_color = self._fig.layout['plot_bgcolor']
            paper_color = self._fig.layout['paper_bgcolor']
            self._fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                                    plot_bgcolor='rgba(0,0,0,0)')
        self._fig.write_image(filename, width=figsize[0], height=figsize[1], scale=scale)
        if transparent:
            self._fig.update_layout(plot_bgcolor=plot_color,
                                    paper_bgcolor=paper_color)


class PlotlyWidget(go.FigureWidget):
    """A wrapper around the ``plotly.graph_objects.FigureWidget`` class."""

    def show(self, *args: Any, **kwargs: Any) -> None:
        """Display the figure.

        Args:
            *args: Variable length argument list to be passed to ``plotly.io.show()``.
            **kwargs: Arbitrary keyword arguments to be passed to ``plotly.io.show()``.
        """
        import plotly.io as pio

        config = {}
        if 'config' not in kwargs.keys():
            config = {'scrollZoom': False,
                      'displayModeBar': False,
                      'editable': False}

        pio.show(self, *args, config=config, **kwargs)

    def savefig(
            self,
            filename: str,
            figsize: Tuple[Optional[int]] = (None, None),
            scale: float = 1,
            transparent: bool = False
    ) -> None:
        """Save the figure as a static image.

        Args:
            filename (str): Name of the file to which the image is saved.
            figsize (tuple): Size of figure in pixels.
            scale (float): Scale factor for non-vectorized image formats.
            transparent (bool): Set the background to transparent.
        """
        if transparent:
            plot_color = self.layout['plot_bgcolor']
            paper_color = self.layout['paper_bgcolor']
            self.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                               plot_bgcolor='rgba(0,0,0,0)')

        self.write_image(filename, width=figsize[0], height=figsize[1], scale=scale)
        if transparent:
            self.update_layout(plot_bgcolor=plot_color,
                               paper_bgcolor=paper_color)
