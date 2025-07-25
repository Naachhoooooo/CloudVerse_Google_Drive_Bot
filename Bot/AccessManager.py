import asyncio
from Bot.database import mark_expired_users, add_pending_user, unban_expired_temporary_blacklist
from Bot.AccessControl import post_access_request_to_group


async def mark_expired_users_and_notify(app):
    while True:
        try:
            newly_expired_users = mark_expired_users()
            for user in newly_expired_users:
                try:
                    await app.bot.send_message(
                        chat_id=user['telegram_id'],
                        text="Your access to the bot has expired. Please request access again by sending /start."
                    )
                    add_pending_user(user['telegram_id'], user['username'], user['first_name'], user['last_name'])
                    await post_access_request_to_group(
                        app, user['telegram_id'], user['username'], user['first_name'], user['last_name']
                    )
                except Exception as e:
                    print(f"Failed to notify expired user {user['telegram_id']}: {e}")
        except Exception as e:
            print(f"Error in mark_expired_users_and_notify: {e}")
        await asyncio.sleep(600)

async def unban_expired_temporary_blacklist_and_notify(app):
    while True:
        try:
            unbanned_users = unban_expired_temporary_blacklist()
            for telegram_id in unbanned_users:
                try:
                    await app.bot.send_message(
                        chat_id=telegram_id,
                        text="Your ban period has ended. You may now use the bot again."
                    )
                except Exception as e:
                    print(f"Failed to notify unbanned user {telegram_id}: {e}")
        except Exception as e:
            print(f"Error in unban_expired_temporary_blacklist_and_notify: {e}")
        await asyncio.sleep(600) 