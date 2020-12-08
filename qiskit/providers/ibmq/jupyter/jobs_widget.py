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
# pylint: disable=protected-access

"""Interactive Jobs widget."""

import datetime
from typing import Union

import ipywidgets as wid
import plotly.graph_objects as go
from qiskit.test.mock.fake_backend import FakeBackend
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend

from ..ibmqbackend import IBMQBackend
from ..visualization.interactive.plotly_wrapper import PlotlyWidget

MONTH_NAMES = {1: 'Jan.',
               2: 'Feb.',
               3: 'Mar.',
               4: 'Apr.',
               5: 'May',
               6: 'June',
               7: 'July',
               8: 'Aug.',
               9: 'Sept.',
               10: 'Oct.',
               11: 'Nov.',
               12: 'Dec.'
               }


def _title_builder(sel_dict: dict) -> str:
    """Build the title string for the jobs table.

    Args:
        sel_dict: Dictionary containing information on jobs.

    Returns:
        HTML string for title.
    """
    if 'day' not in sel_dict.keys():
        title_str = 'Jobs in {mon} {yr} ({num})'.format(mon=MONTH_NAMES[sel_dict['month']],
                                                        yr=sel_dict['year'],
                                                        num=len(sel_dict['jobs']))
    else:
        title_str = 'Jobs on {day} {mon} {yr} ({num})'.format(day=sel_dict['day'],
                                                              mon=MONTH_NAMES[sel_dict['month']],
                                                              yr=sel_dict['year'],
                                                              num=len(sel_dict['jobs']))
    return "<h4>{}</h4>".format(title_str)


def _job_table_builder(sel_dict: dict) -> str:
    """Build the job table.

    Args:
        sel_dict: Dictionary containing information on jobs.

    Returns:
        HTML string for job table.
    """
    table_html = "<table>"
    table_html += """<style>
table {
    width: auto !important;
    font-family:IBM Plex Sans, Arial, sans-serif !important;
}

th, td {
    text-align: left !important;
    padding: 5px !important;
}

tr:nth-child(even) {background-color: #f6f6f6 !important;}
</style>"""

    table_html += "<tr><th>Date</th><th>Job ID / Name</th><th>Status</th></tr>"
    table_footer = "</table>"

    for jdata in sel_dict['jobs']:
        date_str = jdata[0].strftime("%H:%M %Z [%d/%b]")
        _temp_str = "<td>{time}</td><td>{jid}</td><td>{status}</td></tr>"
        # job has a name
        if jdata[2]:
            name = "{name} [{jid}]".format(name=jdata[2],
                                           jid=jdata[1])
        else:
            name = jdata[1]
        table_html += _temp_str.format(time=date_str,
                                       jid=name,
                                       status=jdata[3])
    table_html += table_footer
    return table_html


def _job_summary(backend: Union[IBMQBackend, FakeBackend]) -> PlotlyWidget:
    """Interactive jobs summary for a backend.

    Args:
        backend: Display jobs summary for this backend.

    Returns:
        A figure for the rendered job summary.
    """
    now = datetime.datetime.now()
    past_year_date = now - datetime.timedelta(days=365)
    date_filter = {'creationDate': {'gt': past_year_date.isoformat()}}
    jobs = backend.jobs(limit=None, db_filter=date_filter)

    num_jobs = len(jobs)
    main_str = "<b>Total Jobs</b><br>{}".format(num_jobs)
    jobs_dates = {}

    for job in jobs:
        _date = job.creation_date()
        _year = _date.year
        _id = job.job_id()
        _name = job.name()
        _status = job.status().name
        if _year not in jobs_dates.keys():
            jobs_dates[_year] = {}

        _month = _date.month
        if _month not in jobs_dates[_year].keys():
            jobs_dates[_year][_month] = {}

        _day = _date.day

        if _day not in jobs_dates[_year][_month].keys():
            jobs_dates[_year][_month][_day] = []
            jobs_dates[_year][_month][_day].append([_date, _id, _name, _status])

        else:
            jobs_dates[_year][_month][_day].append([_date, _id, _name, _status])
    labels = [main_str]
    parents = [""]
    values = [num_jobs]

    colors = ['#003f5c', '#ffa600', '#2f4b7c', '#f95d6a',
              '#665191', '#ff7c43', '#a05195', '#d45087']

    num_colors = len(colors)

    wedge_colors = ["#FFFFFF"]

    month_counter = 0
    index_jobs = [{}]
    for yr_key, yr_dict in jobs_dates.items():
        # Do the months
        for key, val in yr_dict.items():
            # Adding the months here.  So the total
            # jobs to include must include all the jobs
            # in all the days in that month.
            month_dict = {'year': yr_key, 'month': key, 'jobs': []}
            total_jobs_month = 0
            for day in val.keys():
                for jjj in val[day]:
                    total_jobs_month += 1
                    month_dict['jobs'].append(jjj)

            # add the month jobs to the index
            index_jobs.append(month_dict)
            # Set the label to the year
            month_label = "{mon} {yr}".format(mon=MONTH_NAMES[int(key)],
                                              yr=yr_key)
            labels.append(month_label)
            # Set the parents to the main str
            parents.append(main_str)
            # Add to the total jobs in that year to values
            values.append(total_jobs_month)
            wedge_colors.append(colors[month_counter % num_colors])
            month_counter += 1
            # Do the days
            day_counter = 0
            for day_num, day_jobs in val.items():
                day_dict = {'year': yr_key, 'month': key,
                            'day': day_num, 'jobs': []}
                day_dict['jobs'].extend(day_jobs)

                index_jobs.append(day_dict)
                _day_num = str(day_num)
                if _day_num[0] == '0':
                    _day_num = _day_num[1:]

                if _day_num[-1] == '1':
                    if _day_num[0] != '1' and len(_day_num) == 1:
                        _day_num = _day_num+'st'
                    else:
                        _day_num = _day_num+'th'
                elif _day_num[-1] == '2':
                    if _day_num[0] != '1' and len(_day_num) == 1:
                        _day_num = _day_num+'nd'
                    else:
                        _day_num = _day_num+'th'
                elif _day_num[-1] == '3':
                    if _day_num[0] != '1' and len(_day_num) == 1:
                        _day_num = _day_num+'rd'
                    else:
                        _day_num = _day_num+'th'
                else:
                    _day_num = _day_num+'th'

                labels.append(_day_num)
                parents.append(month_label)
                values.append(len(day_jobs))
                wedge_colors.append(colors[day_counter % num_colors])
                day_counter += 1

    wedge_str = "<b>{label}</b><br><b>{value} Jobs</b>"

    hover_text = [None]+[wedge_str.format(label=labels[kk],
                                          value=values[kk]) for kk in range(1, len(labels))]

    fig = go.Figure(go.Sunburst(labels=labels,
                                parents=parents,
                                values=values,
                                branchvalues="total",
                                textfont=dict(size=18),
                                outsidetextfont=dict(size=20),
                                maxdepth=2,
                                hoverinfo="text",
                                hovertext=hover_text,
                                marker=dict(colors=wedge_colors),
                                )
                    )
    fig.update_layout(margin=dict(t=10, l=10, r=10, b=10))
    sun_wid = PlotlyWidget(fig)
    sun_wid._active = 0
    sun_wid._job_index = index_jobs

    def callback(trace, selection, _):  # pylint: disable=unused-argument
        idx = selection.point_inds[0]
        if idx != sun_wid._active:
            if idx:
                sun_wid._title.value = _title_builder(sun_wid._job_index[idx])
                sun_wid._table.value = _job_table_builder(sun_wid._job_index[idx])
            else:
                sun_wid._title.value = '<h4>Click graph to display jobs</h4>'
                sun_wid._table.value = ''
            sun_wid._active = idx

    sun = sun_wid.data[0]
    sun.on_click(callback)
    return sun_wid


def jobs_tab(backend: Union[IBMQBackend, FakeBackend]) -> wid.HBox:
    """Construct a widget containing job information for an input backend.

    Args:
        backend: Input backend.

    Returns:
        An widget containing job summary.
    """
    title = wid.HTML('<h4>Click graph to display jobs</h4>')
    table = wid.HTML('', layout=wid.Layout(max_height='500px',
                                           height='500px',
                                           width='100%',
                                           overflow='hidden scroll',))

    sun_wid = _job_summary(backend)
    sun_wid._table = table
    sun_wid._title = title

    left = wid.Box(children=[sun_wid],
                   layout=wid.Layout(width='40%',
                                     overflow='hidden hidden'))

    right = wid.VBox(children=[title, table],
                     layout=wid.Layout(width='60%',
                                       overflow='hidden hidden'))

    out = wid.HBox(children=[left, right],
                   layout=wid.Layout(max_height='500px',
                                     margin='10px'))
    return out
