
# regenerate personalized contexts from source files
personalize: user.reload_personalizations()

show talon list report (<phrase>):
    user.show_talon_list_report(user.formatted_text(phrase, "SNAKE_CASE"))
