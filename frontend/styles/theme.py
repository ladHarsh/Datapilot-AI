from styles.colors import (
    LIGHT_THEME,
    DARK_THEME
)


def get_theme(theme_name):

    if theme_name == "Dark":

        return DARK_THEME

    return LIGHT_THEME