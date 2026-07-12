// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jcputhrottle;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.Group;
import javafx.scene.Scene;
import javafx.scene.text.Text;
import javafx.stage.Stage;

import java.awt.*;
import java.awt.event.ActionListener;
import java.awt.image.BufferedImage;

/**
 * @author Bernard Ladenthin bernard.ladenthin@gmail.com
 */
public class Main extends Application {

    public static void main(String[] args) {
        launch(args);
    }

    @Override
    public void start(final Stage window) throws Exception {
        if (!SystemTray.isSupported()) {
            throw new RuntimeException("!SystemTray.isSupported()");
        }

        Scene scene = new Scene(new Group(new Text(20, 20, "Hello World!")));
        window.setTitle("system tray example");
        window.setScene(scene);
        window.sizeToScene();

        Platform.setImplicitExit(false);

        ActionListener listenerShow = e -> Platform.runLater(() -> window.show());
        ActionListener listenerClose = e -> System.exit(0);
        window.setOnCloseRequest(arg0 -> window.hide());

        PopupMenu popup = new PopupMenu();
        MenuItem showItem = new MenuItem("Open");
        MenuItem exitItem = new MenuItem("Close");

        showItem.addActionListener(listenerShow);
        exitItem.addActionListener(listenerClose);

        popup.add(showItem);
        popup.add(exitItem);

        final TrayIcon trayIcon = new TrayIcon(getIcon());
        trayIcon.setPopupMenu(popup);
        trayIcon.addActionListener(e -> Platform.runLater(() -> window.show()));

        SystemTray tray = SystemTray.getSystemTray();
        tray.add(trayIcon);
        window.show();
    }

    public BufferedImage getIcon() {
        BufferedImage image = new BufferedImage(16, 16, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g2d = image.createGraphics();

        g2d.setPaint(new Color(255, 192, 0));
        g2d.fillRect(0, 0, image.getWidth(), image.getHeight());

        g2d.setPaint(new Color(0, 0, 0));
        g2d.drawString("100%", 0, 0);
        g2d.dispose();
        return image;
    }
}