<?xml version='1.0'?>
<!DOCTYPE xsl:stylesheet
[
]>
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">

<!-- this stylesheet upgrades configuration files from Flumotion < 0.3.2 -->
<xsl:output method="xml" indent="yes" />

  <!-- fix up component version -->
  <xsl:template match="//planet/*/component/@version">
    <xsl:attribute name="version">0.3.2</xsl:attribute>
  </xsl:template>

  <!-- fix up component type strings -->
  <xsl:template match="//planet/*/component/@type">
    <xsl:attribute name="type">
      <xsl:choose>
        <xsl:when test=". = 'audiotest'"
          >audiotest-producer</xsl:when>
        <xsl:when test=". = 'disker'"
          >disk-consumer</xsl:when>
        <xsl:when test=". = 'firewire'"
          >firewire-producer</xsl:when>
        <xsl:when test=". = 'gdptestsrc'"
          >gdp-producer</xsl:when>
        <xsl:when test=". = 'htpasswdcrypt'"
          >htpasswdcrypt-bouncer</xsl:when>
        <xsl:when test=". = 'httpfile'"
          >http-server</xsl:when>
        <xsl:when test=". = 'looper'"
          >loop-producer</xsl:when>
        <xsl:when test=". = 'overlay'"
          >overlay-converter</xsl:when>
        <xsl:when test=". = 'preview'"
          >preview-consumer</xsl:when>
        <xsl:when test=". = 'saltsha256'"
          >saltsha256-bouncer</xsl:when>
        <xsl:when test=". = 'soundcard'"
          >soundcard-producer</xsl:when>
        <xsl:when test=". = 'tv-card'"
          >tvcard-producer</xsl:when>
        <xsl:when test=". = 'videotest'"
          >videotest-producer</xsl:when>
        <xsl:when test=". = 'web-cam'"
          >webcam-producer</xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="." />
        </xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
  </xsl:template>

  <!-- fix up property name strings -->
  <xsl:template match="//planet/*/component/property/@name">
    <xsl:attribute name="name">
      <xsl:choose>
        <!-- disker -->
        <xsl:when test=". = 'rotateType'"
          >rotate-type</xsl:when>
        <!-- firewire -->
        <xsl:when test=". = 'scaled_width'"
          >scaled-width</xsl:when>
        <xsl:when test=". = 'is_square'"
          >is-square</xsl:when>
        <!-- http-streamer -->
        <xsl:when test=". = 'issuer'"
          >issuer-class</xsl:when>
        <xsl:when test=". = 'mount_point'"
          >mount-point</xsl:when>
        <xsl:when test=". = 'socket_path'"
          >socket-path</xsl:when>
        <xsl:when test=". = 'porter_socket_path'"
          >porter-socket-path</xsl:when>
        <xsl:when test=". = 'porter_username'"
          >porter-username</xsl:when>
        <xsl:when test=". = 'porter_password'"
          >porter-password</xsl:when>
        <xsl:when test=". = 'user_limit'"
          >client-limit</xsl:when>
        <xsl:when test=". = 'bandwidth_limit'"
          >bandwidth-limit</xsl:when>
        <xsl:when test=". = 'burst_on_connect'"
          >burst-on-connect</xsl:when>
        <xsl:when test=". = 'burst_size'"
          >burst-size</xsl:when>
        <xsl:when test=". = 'burst_time'"
          >burst-time</xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="." />
        </xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
  </xsl:template>

  <!-- fix up theora bitrate to be in bps instead of kbps -->
  <xsl:template match="//planet/*/component/property[@name='bitrate']" priority="9">
      <xsl:if test="../@type = 'theora-encoder' and number(text()) &lt; 10000">
        <property name="bitrate"><xsl:value-of select="." />000</property>
      </xsl:if>
  </xsl:template>

  <!-- Copy all the other nodes -->
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
