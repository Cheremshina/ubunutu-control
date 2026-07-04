import paramiko

def main(host, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(host, username=user, password=password)
        print("✓ Подключено!\n")

        while True:
            cmd = input(f"{user}@{host}$ ").strip()

            if cmd in ['exit', 'quit']:
                break

            if not cmd:
                continue

            # Если команда начинается с 'sudo', используем специальную обработку
            if cmd.startswith('sudo '):
                # Добавляем -S и автоматический ввод пароля
                sudo_cmd = f"echo '{password}' | sudo -S {cmd[5:]}"
                stdin, stdout, stderr = client.exec_command(sudo_cmd)
            else:
                stdin, stdout, stderr = client.exec_command(cmd)

            # Выводим результат
            output = stdout.read().decode()
            error = stderr.read().decode()

            if output:
                print(output.rstrip())
            if error and "password" not in error.lower():
                print(f"STDERR: {error.rstrip()}")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()