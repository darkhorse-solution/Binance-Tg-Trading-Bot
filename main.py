from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
import os
from datetime import datetime


# Config
class Config:
    BOT_TOKEN = "8151983253:AAH3kJebKs89moyrmzFv4JW09kSm4hbPhFQ"
    # CHANNEL_ID = -1001717037581
    CHANNEL_ID = -1002222736366
    API_ID = 24876084
    API_HASH = "a1934a433c25897914d5c23803a38444"


# Session string (replace with your session string)
session = StringSession('')


def parse_trading_signal(message: str):
    try:
        # Split message into lines and remove empty lines
        lines = [line.strip() for line in message.split('\n') if line.strip()]
        # First line should contain trading pair and leverage
        first_line = lines[0]
        # Look for trading pair (any word containing /)
        symbol = next((word for word in first_line.split() if '/' in word), None)
        if not symbol:
            return None
        # Position type
        position_type = 'LONG' if 'Long' in first_line else 'SHORT' if 'Short' in first_line else None
        if not position_type:
            return None
        # Find leverage (number followed by x)
        leverage = None
        for word in first_line.split():
            if 'x' in word.lower():
                try:
                    leverage = int(''.join(filter(str.isdigit, word)))
                    break
                except:
                    continue
        if not leverage:
            return None

        # Entry price - look for number in second line
        try:
            entry_price = float(''.join(c for c in lines[1].split('-')[1] if c.isdigit() or c == '.'))
        except:
            return None

        # Take profit levels - look for numbers and percentages
        tp_levels = []
        for line in lines[3:7]:  # Expect 4 TP levels
            try:
                # Find first number in line for price
                numbers = ''.join(c for c in line if c.isdigit() or c == '.')
                price = float(numbers)

                # Find percentage
                percentage = int(''.join(filter(str.isdigit, line.split('(')[1].split('%')[0])))

                tp_levels.append({
                    'price': price,
                    'percentage': percentage
                })
            except:
                continue

        if len(tp_levels) != 4:
            return None

        return {
            'symbol': symbol,
            'position_type': position_type,
            'leverage': leverage,
            'entry_price': entry_price,
            'take_profit_levels': tp_levels
        }

    except Exception as e:
        print(f"Error parsing message: {e}")
        return None


async def main():
    print('Initializing...')
    client = TelegramClient(
        session,
        Config.API_ID,
        Config.API_HASH,
        connection_retries=5,
        use_ipv6=True,
        timeout=30
    )

    @client.on(events.NewMessage(chats=[Config.CHANNEL_ID]))
    async def handler(event):
        if event.message.reply_to:
            # print("Ignoring replied message")
            return

        message = event.message
        signal = parse_trading_signal(message.text)
        print(message)

        if signal:
            # Format the extracted information
            formatted_message = (
                f"🎯 New Trading Signal\n\n"
                f"Symbol: {signal['symbol']}\n"
                f"Position: {signal['position_type']}\n"
                f"Leverage: {signal['leverage']}x\n"
                f"Entry Price: {signal['entry_price']}\n\n"
                f"Take Profit Levels:\n"
            )

            for i, tp in enumerate(signal['take_profit_levels'], 1):
                formatted_message += f"TP{i}: {tp['price']} ({tp['percentage']}%)\n"

            # Send formatted message to your channel
            try:
                await client.send_message(-1002356346200, formatted_message)
                print("Signal processed and forwarded successfully!")
            except Exception as e:
                print(f"Error sending message: {e}")
        else:
            print("Message received but not a valid trading signal")

    try:
        print('Connecting...')
        await client.connect()

        print('Starting authentication...')
        if not await client.is_user_authorized():
            # Phone number authentication
            phone = input('Phone number (include country code, e.g., +1234567890): ')
            print('Sending code to:', phone)
            await client.send_code_request(phone)

            # Code verification
            print('Waiting for code input...')
            code = input('Enter the code you received: ')
            await client.sign_in(phone, code)

            if await client.is_user_authorized():
                print('Authentication successful!')
                print('\nYour session string (save this):', client.session.save())

        print('Listening for new messages...')
        await client.run_until_disconnected()

    except Exception as error:
        print('Detailed error:', str(error))
        raise error

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
