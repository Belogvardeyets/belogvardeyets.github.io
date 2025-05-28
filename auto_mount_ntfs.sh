#!/bin/bash

# Настройки
DEVICE="/dev/disk2s1"
MOUNT_POINT="/Volumes/SonySD"
NTFS3G_PATH="/usr/local/bin/ntfs-3g"

# Проверка наличия ntfs-3g
if [ ! -x "$NTFS3G_PATH" ]; then
  echo "ntfs-3g не найден по пути $NTFS3G_PATH"
  exit 1
fi

# Создание точки монтирования, если её нет
if [ ! -d "$MOUNT_POINT" ]; then
  echo "Создаю точку монтирования: $MOUNT_POINT"
  sudo mkdir -p "$MOUNT_POINT"
fi

# Отмонтировать диск, если уже смонтирован
if mount | grep "$DEVICE" > /dev/null; then
  echo "Диск уже смонтирован, отмонтирую..."
  sudo umount "$DEVICE"
fi

# Монтирование с ntfs-3g
echo "Монтирую $DEVICE в $MOUNT_POINT через ntfs-3g..."
sudo "$NTFS3G_PATH" "$DEVICE" "$MOUNT_POINT" -o local -o allow_other -o auto_xattr -o auto_cache

# Проверка успеха
if mount | grep "$MOUNT_POINT" > /dev/null; then
  echo "✅ Успешно смонтирован: $MOUNT_POINT"
else
  echo "❌ Ошибка монтирования"
  exit 2
fi
