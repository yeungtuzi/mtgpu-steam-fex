#include "campaign.h"
#include "launch.h"

#include <QApplication>
#include <QComboBox>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QStatusBar>
#include <QTableWidget>
#include <QVBoxLayout>
#include <QWidget>

#include <cstdio>
#include <string>
#include <vector>

static rl::Campaign g_campaign;

static void FillTable(QTableWidget* table, const QString& filter) {
    table->setRowCount(0);
    int launchable = 0;
    for (const auto& m : g_campaign.missions) if (m.Launchable()) ++launchable;
    fprintf(stderr, "FillTable: missions=%zu launchable=%d filter='%s'\n",
            g_campaign.missions.size(), launchable, filter.toUtf8().constData());
    const QString f = filter.trimmed();
    for (const auto& m : g_campaign.missions) {
        if (!m.Launchable()) continue;
        const QString name = QString::fromStdString(m.name);
        const QString pack = QString::fromStdString(m.packName);
        if (!f.isEmpty() && !name.contains(f, Qt::CaseInsensitive) &&
            !pack.contains(f, Qt::CaseInsensitive))
            continue;
        const int row = table->rowCount();
        table->insertRow(row);
        table->setItem(row, 0, new QTableWidgetItem(name));
        table->setItem(row, 1, new QTableWidgetItem(pack));
        table->setItem(row, 2, new QTableWidgetItem(QString::fromStdString(m.side)));
        table->setItem(row, 3, new QTableWidgetItem(QString::fromStdString(m.difficulty)));
    }
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    const std::string root = argc > 1 ? argv[1] : "/home/lf/文档/ra2reunion";

    QWidget win;
    win.setWindowTitle("Reunion Lite (Qt)");
    win.resize(1000, 650);

    auto* search = new QLineEdit(&win);
    search->setPlaceholderText("搜索任务名 / 任务包 / 场景");
    auto* rescan = new QPushButton("重新扫描", &win);
    auto* launch = new QPushButton("启动游戏", &win);
    auto* table = new QTableWidget(&win);
    table->setColumnCount(4);
    table->setHorizontalHeaderLabels({"任务", "任务包", "阵营", "难度"});
    table->horizontalHeader()->setStretchLastSection(true);
    table->setSelectionBehavior(QAbstractItemView::SelectRows);
    table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    auto* status = new QStatusBar(&win);

    auto* top = new QHBoxLayout;
    top->addWidget(search, 1);
    top->addWidget(rescan);
    top->addWidget(launch);

    auto* layout = new QVBoxLayout(&win);
    layout->addLayout(top);
    layout->addWidget(table, 1);
    layout->addWidget(status);

    auto doScan = [&]() {
        g_campaign = rl::ScanCampaigns(root);
        FillTable(table, search->text());
        status->showMessage(
            QString("任务包 %1 / 任务 %2 / 问题 %3")
                .arg(g_campaign.packs.size())
                .arg(g_campaign.missions.size())
                .arg(g_campaign.issues.size()));
    };

    QObject::connect(search, &QLineEdit::textChanged, [&](const QString& t) { FillTable(table, t); });
    QObject::connect(rescan, &QPushButton::clicked, doScan);
    QObject::connect(launch, &QPushButton::clicked, [&]() {
        status->showMessage("启动逻辑移植中（下一步：runprep + gamemd）");
    });

    doScan();
    win.show();
    return app.exec();
}
