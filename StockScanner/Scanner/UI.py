from flask import Flask, render_template_string
import sqlite3
import time
from threading import Thread

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Stock Scanner</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f5f5f5; }
        .positive { color: green; }
        .negative { color: red; }
        .super-mover { background-color: #ffeeba; }
        .super-volume { background-color: #d1ecf1; }
        h2 { color: #333; margin-top: 30px; }
    </style>
    <script>
        function refreshData() {
            fetch('/data')
                .then(response => response.text())
                .then(html => {
                    document.getElementById('content').innerHTML = html;
                });
        }
        setInterval(refreshData, 5000);
    </script>
</head>
<body>
    <div id="content">
        {{ content | safe }}
    </div>
</body>
</html>
'''


DATA_TEMPLATE = '''
<h2>Top 10 Percent Movers</h2>
<table>
    <tr>
        <th>Ticker</th>
        <th>Price</th>
        <th>% Change</th>
        <th>Vol Ratio</th>
    </tr>
    {% for row in percent_movers %}
    <tr class="{{ 'super-mover' if row[2] > 20 and row[3] > 10 else '' }}">
        <td><a href="https://www.tradingview.com/chart/oMIGAAyf/?symbol={{ row[0] }}" onclick="window.open(this.href, 'TradingView', 'width=1200,height=800'); return false;">{{ row[0] }}</a></td>
        <td>${{ "%.2f"|format(row[1]) }}</td>
        <td class="{{ 'positive' if row[2] > 0 else 'negative' }}">{{ "%.2f"|format(row[2]) }}%</td>
        <td>{{ "%.2f"|format(row[3]) }}</td>
    </tr>
    {% endfor %}
</table>

<h2>Top 10 Volume Movers</h2>
<table>
    <tr>
        <th>Ticker</th>
        <th>Price</th>
        <th>% Change</th>
        <th>Vol Ratio</th>
    </tr>
    {% for row in volume_movers %}
    <tr class="{{ 'super-volume' if row[2] > 20 and row[3] > 10 else '' }}">
        <td><a href="https://www.tradingview.com/chart/oMIGAAyf/?symbol={{ row[0] }}" onclick="window.open(this.href, 'TradingView', 'width=1200,height=800'); return false;">{{ row[0] }}</a></td>
        <td>${{ "%.2f"|format(row[1]) }}</td>
        <td class="{{ 'positive' if row[2] > 0 else 'negative' }}">{{ "%.2f"|format(row[2]) }}%</td>
        <td>{{ "%.2f"|format(row[3]) }}</td>
    </tr>
    {% endfor %}
</table>
<p>Last updated: {{ last_update }}</p>
'''
def get_stock_data():
    conn = sqlite3.connect("stock_data.db")
    cursor = conn.cursor()

    base_conditions = """
    WHERE latest_price > 1 
    AND latest_price < 20 
    AND daily_volume > 100000
    """

    percent_query = f"""
    SELECT ticker, latest_price, percent_change, volume_ratio
    FROM stocks
    {base_conditions}
    ORDER BY percent_change DESC
    LIMIT 10
    """

    volume_query = f"""
    SELECT ticker, latest_price, percent_change, volume_ratio
    FROM stocks
    {base_conditions}
    ORDER BY volume_ratio DESC
    LIMIT 10
    """

    cursor.execute(percent_query)
    percent_movers = cursor.fetchall()

    cursor.execute(volume_query)
    volume_movers = cursor.fetchall()

    conn.close()
    return percent_movers, volume_movers

@app.route('/')
def home():
    percent_movers, volume_movers = get_stock_data()
    content = render_template_string(DATA_TEMPLATE,
                                     percent_movers=percent_movers,
                                     volume_movers=volume_movers,
                                     last_update=time.strftime('%H:%M:%S'))
    return render_template_string(HTML_TEMPLATE, content=content)


@app.route('/data')
def data():
    percent_movers, volume_movers = get_stock_data()
    return render_template_string(DATA_TEMPLATE,
                                  percent_movers=percent_movers,
                                  volume_movers=volume_movers,
                                  last_update=time.strftime('%H:%M:%S'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)