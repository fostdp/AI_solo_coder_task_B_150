import { useState, useEffect } from 'react'
import { Layout, Menu, Select, Button, Drawer, Tag, Space } from 'antd'
import {
  DashboardOutlined,
  BarChartOutlined,
  AlertOutlined,
  SettingOutlined,
  RobotOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ExperimentOutlined,
  DatabaseOutlined,
  SwapOutlined,
  ClockCircleOutlined,
  UnorderedListOutlined,
  CarOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { WoodOxScene } from './components/WoodOxScene'
import { SensorDataPanel } from './components/SensorDataPanel'
import { ControlPanel } from './components/ControlPanel'
import { AlertPanel } from './components/AlertPanel'
import { TransportComparison } from './components/TransportComparison'
import { EraComparison } from './components/EraComparison'
import { CargoStabilityPanel } from './components/CargoStabilityPanel'
import { VirtualDriving } from './components/VirtualDriving'
import { useAppStore } from './store/useAppStore'
import { useWebSocket } from './hooks/useWebSocket'
import { systemApi } from './utils/api'
import './index.css'

const { Header, Sider, Content } = Layout

type TabKey = 'realtime' | 'simulation' | 'analysis' | 'alerts' | 'history' | 'settings'
  | 'transport_compare' | 'era_compare' | 'cargo_stability' | 'virtual_driving'

const menuItems: MenuProps['items'] = [
  { key: 'realtime', icon: <DashboardOutlined />, label: '实时监控' },
  { key: 'simulation', icon: <RobotOutlined />, label: '行走仿真' },
  { key: 'analysis', icon: <BarChartOutlined />, label: '越障分析' },
  { key: 'alerts', icon: <AlertOutlined />, label: '告警中心' },
  { key: 'history', icon: <DatabaseOutlined />, label: '历史数据' },
  {
    key: 'feature_group',
    icon: <ExperimentOutlined />,
    label: '扩展功能',
    children: [
      { key: 'transport_compare', icon: <SwapOutlined />, label: '古代运输工具对比' },
      { key: 'era_compare', icon: <ClockCircleOutlined />, label: '跨时代机器人对比' },
      { key: 'cargo_stability', icon: <UnorderedListOutlined />, label: '货箱装载稳定性' },
      { key: 'virtual_driving', icon: <CarOutlined />, label: '虚拟驾驶体验' },
    ],
  },
  { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
]

const devices = [
  { value: 'woodox_001', label: '木牛流马一号原型机' },
  { value: 'woodox_002', label: '木牛流马二号原型机' },
  { value: 'woodox_003', label: '木牛流马三号原型机' },
]

function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [activeTab, setActiveTab] = useState<TabKey>('realtime')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [systemInfo, setSystemInfo] = useState<any>(null)

  const { selectedDevice, setSelectedDevice, alerts, wsConnected } = useAppStore()

  useWebSocket({
    deviceId: selectedDevice,
  })

  useEffect(() => {
    const fetchSystemInfo = async () => {
      try {
        const res = await systemApi.getInfo()
        setSystemInfo(res.data)
      } catch (error) {
        console.error('获取系统信息失败:', error)
      }
    }
    fetchSystemInfo()
  }, [])

  const activeAlertsCount = alerts.filter((a) => !a.acknowledged).length

  const renderContent = () => {
    switch (activeTab) {
      case 'realtime':
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 space-y-4">
              <div className="bg-white rounded-lg shadow overflow-hidden" style={{ height: 600 }}>
                <WoodOxScene />
              </div>
              <SensorDataPanel />
            </div>
            <div className="space-y-4">
              <ControlPanel />
            </div>
          </div>
        )

      case 'simulation':
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 space-y-4">
              <div className="bg-white rounded-lg shadow overflow-hidden" style={{ height: 600 }}>
                <WoodOxScene />
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <ExperimentOutlined className="text-blue-500" />
                  步态分析结果
                </h3>
                <p className="text-gray-500">点击"计算步态参数"按钮开始仿真分析</p>
              </div>
            </div>
            <div className="space-y-4">
              <ControlPanel />
            </div>
          </div>
        )

      case 'analysis':
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 space-y-4">
              <div className="bg-white rounded-lg shadow overflow-hidden" style={{ height: 600 }}>
                <WoodOxScene />
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <BarChartOutlined className="text-green-500" />
                  越障能力评估报告
                </h3>
                <p className="text-gray-500">设置障碍高度后点击"评估越障能力"按钮</p>
              </div>
            </div>
            <div className="space-y-4">
              <ControlPanel />
            </div>
          </div>
        )

      case 'alerts':
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <div className="bg-white rounded-lg shadow overflow-hidden" style={{ height: 600 }}>
                <WoodOxScene />
              </div>
            </div>
            <div>
              <AlertPanel />
            </div>
          </div>
        )

      case 'history':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">历史数据查询</h2>
            <SensorDataPanel />
          </div>
        )

      case 'settings':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">系统设置</h2>
            {systemInfo && (
              <div className="space-y-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <h3 className="font-medium mb-2">系统信息</h3>
                  <p>名称: {systemInfo.name}</p>
                  <p>版本: {systemInfo.version}</p>
                  <p>环境: {systemInfo.environment}</p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <h3 className="font-medium mb-2">功能模块</h3>
                  <div className="flex flex-wrap gap-2">
                    {systemInfo.features?.map((feature: string, i: number) => (
                      <Tag key={i} color="blue">{feature}</Tag>
                    ))}
                  </div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <h3 className="font-medium mb-2">告警阈值设置</h3>
                  <p>机身倾角阈值: ±{systemInfo.alert_thresholds?.inclination}°</p>
                  <p>机构卡死阈值: {systemInfo.alert_thresholds?.mechanism_jam}mm</p>
                </div>
              </div>
            )}
          </div>
        )

      case 'transport_compare':
        return <TransportComparison />

      case 'era_compare':
        return <EraComparison />

      case 'cargo_stability':
        return <CargoStabilityPanel />

      case 'virtual_driving':
        return <VirtualDriving />

      default:
        return null
    }
  }

  return (
    <Layout className="min-h-screen">
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="dark"
        className="bg-gradient-to-b from-amber-900 to-amber-950"
      >
        <div className="h-16 flex items-center justify-center px-4 border-b border-amber-800">
          <div className="flex items-center gap-3">
            <RobotOutlined className="text-2xl text-amber-400" />
            {!collapsed && (
              <div>
                <div className="text-white font-bold text-sm">木牛流马</div>
                <div className="text-amber-300 text-xs">仿真分析系统</div>
              </div>
            )}
          </div>
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[activeTab]}
          items={menuItems}
          onClick={({ key }) => setActiveTab(key as TabKey)}
          className="bg-transparent border-0 mt-2"
        />

        {activeAlertsCount > 0 && !collapsed && (
          <div className="absolute bottom-4 left-4 right-4">
            <div className="bg-red-600 text-white text-center py-2 px-3 rounded-lg text-sm animate-pulse">
              <AlertOutlined className="mr-1" />
              {activeAlertsCount} 个活动告警
            </div>
          </div>
        )}
      </Sider>

      <Layout>
        <Header className="bg-white px-4 shadow-sm flex items-center justify-between h-16">
          <div className="flex items-center gap-4">
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              className="mr-4 hidden md:block"
            />
            <h1 className="text-lg font-semibold text-gray-800">
              {menuItems.find((item) => item?.key === activeTab)?.label as string}
            </h1>
          </div>

          <div className="flex items-center gap-4">
            <Space>
              <Tag color={wsConnected ? 'success' : 'error'}>
                {wsConnected ? '● WebSocket连接' : '● 连接断开'}
              </Tag>
              <Select
                value={selectedDevice}
                onChange={setSelectedDevice}
                style={{ width: 200 }}
                options={devices}
                size="small"
              />
            </Space>

            <Button
              type="text"
              icon={<MenuFoldOutlined />}
              className="md:hidden"
              onClick={() => setMobileMenuOpen(true)}
            />
          </div>
        </Header>

        <Content className="p-4 bg-gray-100 overflow-auto">
          {renderContent()}
        </Content>
      </Layout>

      <Drawer
        title="导航菜单"
        placement="right"
        onClose={() => setMobileMenuOpen(false)}
        open={mobileMenuOpen}
        width={280}
      >
        <Menu
          mode="inline"
          selectedKeys={[activeTab]}
          items={menuItems}
          onClick={({ key }) => {
            setActiveTab(key as TabKey)
            setMobileMenuOpen(false)
          }}
        />
      </Drawer>
    </Layout>
  )
}

export default App
