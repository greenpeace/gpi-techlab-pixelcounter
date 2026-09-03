(function ($) {
  'use strict';

  function optionsFor(table) {
    var $table = $(table);
    var orderColumn = Number($table.data('order-column'));
    var orderDirection = $table.data('order-direction') || 'asc';
    var paging = $table.data('paging') !== false;
    var options = {
      stateSave: true,
      stateDuration: 604800,
      pageLength: 10,
      paging: paging,
      searching: true,
      ordering: true,
      info: paging,
      autoWidth: false
    };
    if (!Number.isNaN(orderColumn)) options.order = [[orderColumn, orderDirection]];
    return options;
  }

  $(function () {
    $('table[data-datatable]').each(function () {
      if (!$.fn.DataTable.isDataTable(this)) {
        $(this).DataTable(optionsFor(this));
      }
    });

    // Persist paging, ordering and search immediately before a form navigates
    // away, so returning after an edit/delete stays on the same table view.
    $(document).on('submit click', 'table[data-datatable] form, table[data-datatable] a', function () {
      var table = $(this).closest('table')[0];
      if (table && $.fn.DataTable.isDataTable(table)) {
        $(table).DataTable().state.save();
      }
    });
  });
})(jQuery);
