from views.assets.generic_hardware_asset import render_generic_hardware_asset


def render_monitor_asset(
    *,
    df_hw,
    admin_mode,
    show_pop_computer,
    add_computer_dialog,
    edit_computer_dialog,
):
    list_name = "Asset Monitor"
    hardware_name = "Monitor"

    render_generic_hardware_asset(
        df_hw=df_hw,
        list_name=list_name,
        hardware_name=hardware_name,
        admin_mode=admin_mode,
        show_pop_computer=show_pop_computer,
        add_computer_dialog=add_computer_dialog,
        edit_computer_dialog=edit_computer_dialog,
    )
