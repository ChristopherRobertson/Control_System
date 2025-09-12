import { ReactNode } from 'react'
import { Box } from '@mui/material'
import Navbar from './Navbar'
import Statusbar from './Statusbar'

interface MainLayoutProps {
  children: ReactNode
}

function MainLayout({ children }: MainLayoutProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Navbar />
      <Box 
        component="main" 
        sx={{ 
          flexGrow: 1, 
          overflow: 'auto',
          backgroundColor: 'background.default',
          p: 3
        }}
      >
        {children}
      </Box>
      <Statusbar />
    </Box>
  )
}

export default MainLayout