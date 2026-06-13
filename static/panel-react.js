(function () {
    function waitForReact(callback) {
        if (window.React && window.ReactDOM) {
            callback(window.React, window.ReactDOM);
            return;
        }
        setTimeout(function () { waitForReact(callback); }, 80);
    }

    function enhanceTables(React, ReactDOM) {
        document.querySelectorAll('table').forEach(function (table, index) {
            if (table.dataset.reactEnhanced === '1') return;
            table.dataset.reactEnhanced = '1';

            var mount = document.createElement('div');
            mount.className = 'react-table-tools';
            table.parentNode.insertBefore(mount, table);

            function TableTools() {
                var _React$useState = React.useState(''), query = _React$useState[0], setQuery = _React$useState[1];
                var _React$useState2 = React.useState(''), estado = _React$useState2[0], setEstado = _React$useState2[1];

                React.useEffect(function () {
                    var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr'));
                    rows.forEach(function (row) {
                        var text = row.textContent.toLowerCase();
                        var okQuery = !query || text.indexOf(query.toLowerCase()) !== -1;
                        var okEstado = !estado || text.indexOf(estado.toLowerCase()) !== -1;
                        row.style.display = okQuery && okEstado ? '' : 'none';
                    });
                }, [query, estado]);

                var hasEstado = Array.prototype.some.call(table.querySelectorAll('th'), function (th) {
                    return th.textContent.trim().toLowerCase() === 'estado';
                });

                return React.createElement('div', { className: 'react-toolbar' },
                    React.createElement('div', { className: 'react-searchbox' },
                        React.createElement('span', null, 'Buscar'),
                        React.createElement('input', {
                            value: query,
                            onChange: function (event) { setQuery(event.target.value); },
                            placeholder: 'Filtrar registros visibles...',
                            'aria-label': 'Filtrar tabla'
                        })
                    ),
                    hasEstado ? React.createElement('div', { className: 'react-filter-pills' },
                        ['Pendiente', 'En proceso', 'Entregado', 'Cancelado'].map(function (item) {
                            return React.createElement('button', {
                                key: item,
                                type: 'button',
                                className: estado === item ? 'pill active' : 'pill',
                                onClick: function () { setEstado(estado === item ? '' : item); }
                            }, item);
                        })
                    ) : null
                );
            }

            ReactDOM.createRoot(mount).render(React.createElement(TableTools));
            document.dispatchEvent(new CustomEvent('jugueteriabot:react-enhanced'));
        });
    }

    function enhanceDashboard(React, ReactDOM) {
        var mount = document.getElementById('dashboard-react-app');
        var dataTag = document.getElementById('dashboard-cards-data');
        var fallback = document.getElementById('dashboard-fallback-cards');
        if (!mount || !dataTag) return;

        var cards = [];
        try { cards = JSON.parse(dataTag.textContent || '[]'); } catch (e) { cards = []; }
        if (!cards.length) return;

        function DashboardCards() {
            var _React$useState = React.useState(''), query = _React$useState[0], setQuery = _React$useState[1];
            var filtered = cards.filter(function (card) {
                var text = (card.title + ' ' + card.description).toLowerCase();
                return text.indexOf(query.toLowerCase()) !== -1;
            });

            React.useEffect(function () {
                if (fallback) fallback.style.display = 'none';
            }, []);

            return React.createElement('section', { className: 'react-dashboard' },
                React.createElement('div', { className: 'react-dashboard-header' },
                    React.createElement('div', null,
                        React.createElement('h2', null, 'Accesos del sistema'),
                        React.createElement('p', null, 'Panel interactivo optimizado para uso del cliente y operación diaria.')
                    ),
                    React.createElement('input', {
                        value: query,
                        onChange: function (event) { setQuery(event.target.value); },
                        placeholder: 'Buscar apartado...',
                        'aria-label': 'Buscar apartado del dashboard'
                    })
                ),
                React.createElement('div', { className: 'cards react-cards' },
                    filtered.map(function (card) {
                        return React.createElement('article', { className: 'card react-card', key: card.href },
                            React.createElement('div', { className: 'card-icon' }, card.icon),
                            React.createElement('h3', null, card.title),
                            React.createElement('p', null, card.description),
                            React.createElement('a', { href: card.href, className: 'btn' }, card.cta)
                        );
                    })
                )
            );
        }

        ReactDOM.createRoot(mount).render(React.createElement(DashboardCards));
        document.dispatchEvent(new CustomEvent('jugueteriabot:react-enhanced'));
    }

    document.addEventListener('DOMContentLoaded', function () {
        waitForReact(function (React, ReactDOM) {
            enhanceDashboard(React, ReactDOM);
            enhanceTables(React, ReactDOM);
        });
    });
}());

// Entradas multiproducto + gráficas de ventas
(function () {
  function initEntradaBuilder() {
    const form = document.getElementById('entrada-form');
    if (!form) return;
    const producto = document.getElementById('entrada-producto');
    const cantidad = document.getElementById('entrada-cantidad');
    const costo = document.getElementById('entrada-costo');
    const btn = document.getElementById('btn-agregar-entrada');
    const tbody = document.querySelector('#tabla-entrada-items tbody');
    const hidden = document.getElementById('items-json');
    const totalSpan = document.getElementById('entrada-total');
    let items = [];

    function render() {
      tbody.innerHTML = '';
      let total = 0;
      items.forEach((item, index) => {
        const subtotal = item.cantidad * item.costo_unitario;
        total += subtotal;
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${item.nombre}</td><td>${item.cantidad}</td><td>$${item.costo_unitario.toFixed(2)}</td><td>$${subtotal.toFixed(2)}</td><td><button type="button" class="btn btn-eliminar" data-index="${index}">Quitar</button></td>`;
        tbody.appendChild(tr);
      });
      hidden.value = JSON.stringify(items.map(({ id_juguete, cantidad, costo_unitario }) => ({ id_juguete, cantidad, costo_unitario })));
      totalSpan.textContent = total.toFixed(2);
    }

    btn.addEventListener('click', function () {
      const option = producto.options[producto.selectedIndex];
      const id = parseInt(producto.value || '0', 10);
      const cant = parseInt(cantidad.value || '0', 10);
      const cost = parseFloat(costo.value || '0');
      const precioVenta = parseFloat(option.dataset.precioVenta || '0');
      if (!id || cant <= 0 || cost < 0) {
        alert('Selecciona producto, cantidad mayor a 0 y costo válido.');
        return;
      }
      if (cost > precioVenta) {
        alert('El precio de compra no puede ser mayor que el precio de venta del producto.');
        return;
      }
      const existente = items.find(i => i.id_juguete === id && i.costo_unitario === cost);
      if (existente) existente.cantidad += cant;
      else items.push({ id_juguete: id, nombre: option.dataset.nombre || option.textContent, cantidad: cant, costo_unitario: cost });
      cantidad.value = '';
      costo.value = '';
      render();
    });

    tbody.addEventListener('click', function (ev) {
      if (ev.target.matches('[data-index]')) {
        items.splice(parseInt(ev.target.dataset.index, 10), 1);
        render();
      }
    });

    form.addEventListener('submit', function (ev) {
      if (items.length === 0) {
        ev.preventDefault();
        alert('Agrega al menos un producto a la entrada.');
      }
    });
  }

  function drawChart(canvasId, dataId) {
    const canvas = document.getElementById(canvasId);
    const dataScript = document.getElementById(dataId);
    if (!canvas || !dataScript || !window.Chart) return;
    let data = [];
    try { data = JSON.parse(dataScript.textContent || '[]'); } catch (_) { data = []; }
    new Chart(canvas, {
      type: 'line',
      data: {
        labels: data.map(x => x.fecha),
        datasets: [
          { label: 'Ventas entregadas', data: data.map(x => x.total), tension: 0.25 },
          { label: 'Ganancia', data: data.map(x => x.ganancia || 0), tension: 0.25 }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initEntradaBuilder();
    drawChart('ventas-chart', 'ventas-chart-data');
    drawChart('dashboard-ventas-chart', 'dashboard-ventas-data');
  });
})();
